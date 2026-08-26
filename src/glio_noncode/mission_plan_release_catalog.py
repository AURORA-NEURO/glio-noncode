"""Deterministic catalogs for multiple public mission-plan releases.

One portable mission-plan release is useful for a handoff.  A research
program also needs to compare and inventory many handoffs without loading
planner internals or trusting a mutable database index.  This module builds a
small, closed catalog from public receipts or independently verified release
directories.  Every entry is reduced to public aggregate fields, ordered
canonically, addressed, and checked for identity collisions.

The optional filesystem form contains six exact-byte artifacts.  A consumer
can verify those bytes on another machine, hydrate the catalog, and query it
without the original release builder.  Catalog operations are descriptive and
read-only: they do not execute workflow steps, authorize a clinical decision,
or publish attribution, language, model, producer, routing, identity, or raw
request metadata.
"""

from __future__ import annotations

import csv
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .mission_plan_release import (
    MissionPlanOfflineRelease,
    MissionPlanReleaseBundle,
    build_mission_plan_release,
    load_mission_plan_release,
)
from .mission_runtime_public import MissionPlanPublicReceipt
from .serialization import canonical_json, content_hash, hash_bytes, jsonable


MISSION_PLAN_RELEASE_CATALOG_VERSION = "mission-plan-release-catalog-v1"
MISSION_PLAN_RELEASE_CATALOG_SCHEMA_VERSION = "mission-plan-release-catalog-schema-v1"
MISSION_PLAN_RELEASE_CATALOG_CAPABILITIES_VERSION = "mission-plan-release-catalog-capabilities-v1"
MISSION_PLAN_RELEASE_CATALOG_MANIFEST_FILE = "manifest.json"
MISSION_PLAN_RELEASE_CATALOG_MAX_ENTRIES = 256
MISSION_PLAN_RELEASE_CATALOG_MAX_ARTIFACTS = 16
MISSION_PLAN_RELEASE_CATALOG_MAX_CHECKS = 16
MISSION_PLAN_RELEASE_CATALOG_REQUIRED_ARTIFACTS = frozenset(
    {
        "catalog-checks.json",
        "catalog-summary.json",
        "manifest.json",
        "mission-plan-release-catalog.csv",
        "mission-plan-release-catalog.json",
        "mission-plan-release-catalog.md",
    }
)

_CATALOG_FORBIDDEN_KEYS = frozenset(
    {
        "agent",
        "agent_id",
        "assistant",
        "author",
        "contact",
        "email",
        "generated_by",
        "identity",
        "language",
        "model",
        "model_id",
        "model_version",
        "patient",
        "producer",
        "programming_language",
        "raw_request",
        "request",
        "secret",
        "subject",
        "token",
        "tool_id",
    }
)


def _text(value: Any, field: str, *, maximum: int = 180) -> str:
    if value is None:
        raise ValidationError(f"{field} must not be empty")
    normalized = str(value).strip()
    if not normalized:
        raise ValidationError(f"{field} must not be empty")
    if len(normalized) > maximum:
        raise ValidationError(f"{field} exceeds the maximum length")
    return normalized


def _mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return {str(key): child for key, child in value.items()}


def _string_tuple(value: Any, field: str, *, maximum: int = 256) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValidationError(f"{field} must be an array")
    if len(value) > maximum:
        raise ValidationError(f"{field} exceeds the maximum item count")
    result = tuple(_text(item, f"{field}[{index}]") for index, item in enumerate(value))
    if len(result) != len(set(result)):
        raise ValidationError(f"{field} must contain unique values")
    return result


def _private_key_paths(value: Any, path: str = "") -> tuple[str, ...]:
    if isinstance(value, Mapping):
        paths: list[str] = []
        for key, child in value.items():
            key_text = str(key)
            child_path = f"{path}.{key_text}" if path else key_text
            if key_text.casefold() in _CATALOG_FORBIDDEN_KEYS:
                paths.append(child_path)
            paths.extend(_private_key_paths(child, child_path))
        return tuple(paths)
    if isinstance(value, (list, tuple)):
        paths: list[str] = []
        for index, child in enumerate(value):
            paths.extend(_private_key_paths(child, f"{path}[{index}]"))
        return tuple(paths)
    return ()


def _safe_filename(value: Any, field: str) -> str:
    filename = _text(value, field, maximum=180)
    path = Path(filename)
    if (
        path.name != filename
        or filename in {".", ".."}
        or "/" in filename
        or "\\" in filename
    ):
        raise ValidationError(f"{field} must be a plain filename")
    return filename


@dataclass(frozen=True, slots=True)
class MissionPlanReleaseCatalogEntry:
    """One public aggregate row in a release catalog."""

    release_id: str
    release_address: str
    plan_id: str
    plan_address: str
    state: str
    decision: str
    accepted: bool
    step_count: int
    optional_step_count: int
    deterministic_step_count: int
    network_step_count: int
    artifact_count: int
    check_count: int
    warning_count: int
    workflow_kinds: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        for field in (
            "release_id",
            "release_address",
            "plan_id",
            "plan_address",
            "state",
            "decision",
            "content_address",
        ):
            _text(getattr(self, field), f"catalog_entry.{field}")
        for field in (
            "step_count",
            "optional_step_count",
            "deterministic_step_count",
            "network_step_count",
            "artifact_count",
            "check_count",
            "warning_count",
        ):
            value = getattr(self, field)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValidationError(f"catalog_entry.{field} must be a non-negative integer")
        if self.optional_step_count > self.step_count:
            raise ValidationError("catalog entry optional step count exceeds step count")
        if self.deterministic_step_count > self.step_count:
            raise ValidationError("catalog entry deterministic step count exceeds step count")
        if self.network_step_count > self.step_count:
            raise ValidationError("catalog entry network step count exceeds step count")
        if len(self.workflow_kinds) > self.step_count:
            raise ValidationError("catalog entry workflow kind count exceeds step count")
        if len(self.workflow_kinds) != len(set(self.workflow_kinds)):
            raise ValidationError("catalog entry workflow kinds must be unique")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "MissionPlanReleaseCatalogEntry":
        body = _mapping(value, "catalog entry")
        allowed = {
            "release_id",
            "release_address",
            "plan_id",
            "plan_address",
            "state",
            "decision",
            "accepted",
            "step_count",
            "optional_step_count",
            "deterministic_step_count",
            "network_step_count",
            "artifact_count",
            "check_count",
            "warning_count",
            "workflow_kinds",
            "content_address",
        }
        unknown = set(body) - allowed
        if unknown:
            raise ValidationError(f"catalog entry contains unsupported fields: {sorted(unknown)}")
        try:
            numbers = {
                field: int(body.get(field))
                for field in (
                    "step_count",
                    "optional_step_count",
                    "deterministic_step_count",
                    "network_step_count",
                    "artifact_count",
                    "check_count",
                    "warning_count",
                )
            }
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValidationError("catalog entry contains invalid counts") from exc
        return cls(
            release_id=_text(body.get("release_id"), "catalog_entry.release_id"),
            release_address=_text(body.get("release_address"), "catalog_entry.release_address"),
            plan_id=_text(body.get("plan_id"), "catalog_entry.plan_id"),
            plan_address=_text(body.get("plan_address"), "catalog_entry.plan_address"),
            state=_text(body.get("state"), "catalog_entry.state"),
            decision=_text(body.get("decision"), "catalog_entry.decision"),
            accepted=bool(body.get("accepted")),
            workflow_kinds=_string_tuple(body.get("workflow_kinds", ()), "catalog_entry.workflow_kinds"),
            content_address=_text(body.get("content_address"), "catalog_entry.content_address"),
            **numbers,
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MissionPlanReleaseCatalogCheck:
    """One catalog integrity or reconciliation check."""

    check_id: str
    category: str
    accepted: bool
    observed: Any
    expected: Any
    message: str
    content_address: str

    def __post_init__(self) -> None:
        _text(self.check_id, "catalog_check.check_id", maximum=120)
        _text(self.category, "catalog_check.category", maximum=64)
        _text(self.message, "catalog_check.message", maximum=360)
        _text(self.content_address, "catalog_check.content_address")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "MissionPlanReleaseCatalogCheck":
        body = _mapping(value, "catalog check")
        allowed = {"check_id", "category", "accepted", "observed", "expected", "message", "content_address"}
        unknown = set(body) - allowed
        if unknown:
            raise ValidationError(f"catalog check contains unsupported fields: {sorted(unknown)}")
        return cls(
            check_id=_text(body.get("check_id"), "catalog_check.check_id", maximum=120),
            category=_text(body.get("category"), "catalog_check.category", maximum=64),
            accepted=bool(body.get("accepted")),
            observed=body.get("observed"),
            expected=body.get("expected"),
            message=_text(body.get("message"), "catalog_check.message", maximum=360),
            content_address=_text(body.get("content_address"), "catalog_check.content_address"),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MissionPlanReleaseCatalog:
    """Addressed, canonically ordered public release catalog."""

    catalog_version: str
    catalog_id: str
    entries: tuple[MissionPlanReleaseCatalogEntry, ...]
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        if self.catalog_version != MISSION_PLAN_RELEASE_CATALOG_VERSION:
            raise ValidationError("catalog version is invalid")
        _text(self.catalog_id, "catalog.catalog_id", maximum=96)
        if len(self.entries) > MISSION_PLAN_RELEASE_CATALOG_MAX_ENTRIES:
            raise ValidationError("catalog entry count exceeds the bound")
        ordering = tuple((item.release_id, item.plan_address) for item in self.entries)
        if ordering != tuple(sorted(ordering)):
            raise ValidationError("catalog entries must be canonically ordered")
        if len({item.release_id for item in self.entries}) != len(self.entries):
            raise ValidationError("catalog release IDs must be unique")
        if len({item.plan_address for item in self.entries}) != len(self.entries):
            raise ValidationError("catalog plan addresses must be unique")
        _text(self.content_address, "catalog.content_address")

    @property
    def entry_count(self) -> int:
        return len(self.entries)

    @property
    def accepted_entry_count(self) -> int:
        return sum(item.accepted for item in self.entries)

    @property
    def rejected_entry_count(self) -> int:
        return self.entry_count - self.accepted_entry_count

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "MissionPlanReleaseCatalog":
        body = _mapping(value, "mission plan release catalog")
        allowed = {
            "catalog_version",
            "catalog_id",
            "entry_count",
            "accepted_entry_count",
            "rejected_entry_count",
            "entries",
            "accepted",
            "content_address",
        }
        unknown = set(body) - allowed
        if unknown:
            raise ValidationError(f"catalog contains unsupported fields: {sorted(unknown)}")
        raw_entries = body.get("entries", ())
        if not isinstance(raw_entries, (list, tuple)):
            raise ValidationError("catalog entries must be an array")
        entries = tuple(MissionPlanReleaseCatalogEntry.from_mapping(item) for item in raw_entries)
        catalog = cls(
            catalog_version=_text(body.get("catalog_version"), "catalog.catalog_version"),
            catalog_id=_text(body.get("catalog_id"), "catalog.catalog_id", maximum=96),
            entries=entries,
            accepted=bool(body.get("accepted")),
            content_address=_text(body.get("content_address"), "catalog.content_address"),
        )
        if body.get("entry_count") != catalog.entry_count:
            raise ValidationError("catalog entry count does not reconcile")
        if body.get("accepted_entry_count") != catalog.accepted_entry_count:
            raise ValidationError("catalog accepted entry count does not reconcile")
        if body.get("rejected_entry_count") != catalog.rejected_entry_count:
            raise ValidationError("catalog rejected entry count does not reconcile")
        if catalog.accepted != all(item.accepted for item in catalog.entries):
            raise ValidationError("catalog acceptance does not reconcile with its entries")
        expected = content_hash(
            {
                "catalog_version": catalog.catalog_version,
                "catalog_id": catalog.catalog_id,
                "entries": catalog.entries,
                "accepted": catalog.accepted,
            },
            prefix="mission-plan-release-catalog",
        )
        if expected != catalog.content_address:
            raise ValidationError("catalog content address does not reconcile")
        return catalog

    def to_dict(self) -> dict[str, Any]:
        body = {
            "catalog_version": self.catalog_version,
            "catalog_id": self.catalog_id,
            "entry_count": self.entry_count,
            "accepted_entry_count": self.accepted_entry_count,
            "rejected_entry_count": self.rejected_entry_count,
            "entries": self.entries,
            "accepted": self.accepted,
        }
        return jsonable(body | {"content_address": self.content_address})


@dataclass(frozen=True, slots=True)
class MissionPlanReleaseCatalogArtifact:
    """One exact-byte catalog artifact."""

    artifact_id: str
    filename: str
    media_type: str
    byte_count: int
    line_count: int
    content_address: str
    payload: bytes

    def __post_init__(self) -> None:
        _text(self.artifact_id, "catalog_artifact.artifact_id", maximum=120)
        _safe_filename(self.filename, "catalog_artifact.filename")
        _text(self.media_type, "catalog_artifact.media_type", maximum=80)
        if self.byte_count != len(self.payload) or self.byte_count < 0:
            raise ValidationError("catalog artifact byte count does not reconcile")
        if self.line_count < 0:
            raise ValidationError("catalog artifact line count must be non-negative")
        if hash_bytes(self.payload, prefix="mission-plan-release-catalog-artifact") != self.content_address:
            raise ValidationError("catalog artifact content address does not reconcile")

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
class MissionPlanReleaseCatalogBundle:
    """Complete in-memory catalog handoff."""

    catalog: MissionPlanReleaseCatalog
    checks: tuple[MissionPlanReleaseCatalogCheck, ...]
    artifacts: tuple[MissionPlanReleaseCatalogArtifact, ...]
    manifest: Mapping[str, Any]
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        if len(self.artifacts) > MISSION_PLAN_RELEASE_CATALOG_MAX_ARTIFACTS:
            raise ValidationError("catalog artifact count exceeds the bound")
        if len(self.checks) > MISSION_PLAN_RELEASE_CATALOG_MAX_CHECKS:
            raise ValidationError("catalog check count exceeds the bound")
        names = tuple(item.filename for item in self.artifacts)
        if len(names) != len(set(names)):
            raise ValidationError("catalog artifact filenames must be unique")
        if not MISSION_PLAN_RELEASE_CATALOG_REQUIRED_ARTIFACTS.issubset(names):
            raise ValidationError("catalog artifacts are incomplete")
        _text(self.content_address, "catalog_bundle.content_address")

    @property
    def catalog_id(self) -> str:
        return self.catalog.catalog_id

    def to_dict(self, *, include_payloads: bool = False) -> dict[str, Any]:
        body = {
            "catalog": self.catalog.to_dict(),
            "checks": self.checks,
            "artifacts": tuple(item.to_dict(include_payload=include_payloads) for item in self.artifacts),
            "manifest": dict(self.manifest),
            "accepted": self.accepted,
        }
        return jsonable(body | {"content_address": self.content_address})


@dataclass(frozen=True, slots=True)
class MissionPlanReleaseCatalogVerification:
    """Independent result of verifying a materialized catalog directory."""

    catalog_id: str
    accepted: bool
    manifest_address_valid: bool
    catalog_address_valid: bool
    checks_address_valid: bool
    summary_address_valid: bool
    artifact_set_valid: bool
    exact_bytes: bool
    public_boundary_valid: bool
    missing_files: tuple[str, ...]
    unexpected_files: tuple[str, ...]
    tampered_files: tuple[str, ...]
    artifact_count: int
    verified_artifact_count: int
    content_address: str

    def __post_init__(self) -> None:
        _text(self.catalog_id, "catalog_verification.catalog_id", maximum=96)
        for field in (
            "missing_files",
            "unexpected_files",
            "tampered_files",
        ):
            values = getattr(self, field)
            if tuple(values) != tuple(sorted(set(values))):
                raise ValidationError(f"{field} must be unique and sorted")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MissionPlanReleaseCatalogOffline:
    """Hydrated catalog loaded from independently verified bytes."""

    catalog: MissionPlanReleaseCatalog
    checks: tuple[MissionPlanReleaseCatalogCheck, ...]
    manifest: Mapping[str, Any]
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        _text(self.catalog.catalog_id, "catalog_offline.catalog_id", maximum=96)
        _text(self.content_address, "catalog_offline.content_address")

    @property
    def catalog_id(self) -> str:
        return self.catalog.catalog_id

    @property
    def entries(self) -> tuple[MissionPlanReleaseCatalogEntry, ...]:
        return self.catalog.entries

    def to_dict(self) -> dict[str, Any]:
        return jsonable(
            {
                "catalog": self.catalog,
                "checks": self.checks,
                "manifest": dict(self.manifest),
                "accepted": self.accepted,
                "content_address": self.content_address,
            }
        )


def _entry_from_bundle(bundle: MissionPlanReleaseBundle) -> MissionPlanReleaseCatalogEntry:
    receipt = bundle.receipt
    kinds = tuple(sorted({step.kind for step in receipt.steps}))
    entry_body = {
        "release_id": bundle.release_id,
        "release_address": bundle.content_address,
        "plan_id": receipt.plan_id,
        "plan_address": receipt.content_address,
        "state": receipt.state.value,
        "decision": receipt.decision,
        "accepted": bundle.accepted,
        "step_count": receipt.step_count,
        "optional_step_count": sum(step.optional for step in receipt.steps),
        "deterministic_step_count": sum(step.deterministic for step in receipt.steps),
        "network_step_count": sum(bool(step.resource.get("network_egress", False)) for step in receipt.steps),
        "artifact_count": len(bundle.artifacts),
        "check_count": len(bundle.checks),
        "warning_count": receipt.warning_count,
        "workflow_kinds": kinds,
    }
    return MissionPlanReleaseCatalogEntry(
        **entry_body,
        content_address=content_hash(entry_body, prefix="mission-plan-release-catalog-entry"),
    )


def _as_bundle(
    value: MissionPlanReleaseBundle | MissionPlanOfflineRelease | MissionPlanPublicReceipt | Mapping[str, Any] | str | Path,
) -> MissionPlanReleaseBundle:
    if isinstance(value, MissionPlanReleaseBundle):
        return value
    if isinstance(value, MissionPlanOfflineRelease):
        return build_mission_plan_release(value.receipt, release_id=value.release_id)
    if isinstance(value, MissionPlanPublicReceipt):
        return build_mission_plan_release(value)
    if isinstance(value, (str, Path)):
        offline = load_mission_plan_release(value)
        return build_mission_plan_release(offline.receipt, release_id=offline.release_id)
    body = _mapping(value, "catalog release source")
    if _private_key_paths(body):
        raise ValidationError("catalog source contains restricted metadata")
    if "receipt" in body:
        raw_receipt = body["receipt"]
        if not isinstance(raw_receipt, Mapping):
            raise ValidationError("catalog source receipt must be an object")
        release_id = None if body.get("release_id") is None else str(body["release_id"])
        return build_mission_plan_release(MissionPlanPublicReceipt.from_mapping(raw_receipt), release_id=release_id)
    if "steps" in body and "content_address" in body:
        return build_mission_plan_release(MissionPlanPublicReceipt.from_mapping(body))
    from .mission_runtime_public import build_public_mission_plan

    return build_mission_plan_release(build_public_mission_plan(body))


def _catalog_check(
    check_id: str,
    category: str,
    accepted: bool,
    observed: Any,
    expected: Any,
    message: str,
) -> MissionPlanReleaseCatalogCheck:
    body = {
        "check_id": check_id,
        "category": category,
        "accepted": bool(accepted),
        "observed": observed,
        "expected": expected,
        "message": message,
    }
    return MissionPlanReleaseCatalogCheck(
        **body,
        content_address=content_hash(body, prefix="mission-plan-release-catalog-check"),
    )


def build_mission_plan_release_catalog(
    values: Iterable[MissionPlanReleaseBundle | MissionPlanOfflineRelease | MissionPlanPublicReceipt | Mapping[str, Any] | str | Path],
    *,
    catalog_id: str = "mission-plan-release-catalog",
) -> MissionPlanReleaseCatalogBundle:
    """Build a deterministic catalog from public release sources."""

    selected_id = _text(catalog_id, "catalog_id", maximum=96)
    sources = tuple(values)
    if not sources:
        raise ValidationError("catalog requires at least one release source")
    if len(sources) > MISSION_PLAN_RELEASE_CATALOG_MAX_ENTRIES:
        raise ValidationError("catalog source count exceeds the bound")
    entries = tuple(sorted((_entry_from_bundle(_as_bundle(value)) for value in sources), key=lambda item: (item.release_id, item.plan_address)))
    release_ids = tuple(item.release_id for item in entries)
    plan_addresses = tuple(item.plan_address for item in entries)
    public_values = jsonable(entries)
    catalog_body = {
        "catalog_version": MISSION_PLAN_RELEASE_CATALOG_VERSION,
        "catalog_id": selected_id,
        "entries": entries,
        "accepted": all(item.accepted for item in entries),
    }
    catalog = MissionPlanReleaseCatalog(
        **catalog_body,
        content_address=content_hash(catalog_body, prefix="mission-plan-release-catalog"),
    )
    checks = (
        _catalog_check(
            "catalog.release_id_uniqueness",
            "identity",
            len(release_ids) == len(set(release_ids)),
            list(release_ids),
            "unique release IDs",
            "Every release ID must identify one catalog entry.",
        ),
        _catalog_check(
            "catalog.plan_address_uniqueness",
            "identity",
            len(plan_addresses) == len(set(plan_addresses)),
            list(plan_addresses),
            "unique plan addresses",
            "Every public plan address must identify one catalog entry.",
        ),
        _catalog_check(
            "catalog.canonical_order",
            "ordering",
            tuple((item.release_id, item.plan_address) for item in entries)
            == tuple(sorted((item.release_id, item.plan_address) for item in entries)),
            [(item.release_id, item.plan_address) for item in entries],
            "release ID then plan address",
            "Entries must be ordered canonically for stable bytes.",
        ),
        _catalog_check(
            "catalog.public_boundary",
            "boundary",
            not bool(_private_key_paths(public_values)),
            (),
            "no restricted metadata paths",
            "Catalog entries must remain inside the public boundary.",
        ),
        _catalog_check(
            "catalog.entry_acceptance",
            "acceptance",
            all(item.accepted for item in entries),
            {"accepted": sum(item.accepted for item in entries), "total": len(entries)},
            "all entries accepted",
            "The catalog is accepted only when every source release is accepted.",
        ),
    )
    catalog_payloads = _catalog_payloads(catalog, checks)
    artifacts = _build_artifacts(catalog_payloads)
    checks_address = content_hash({"checks": checks}, prefix="mission-plan-release-catalog-checks")
    summary_body = {
        "summary_version": "mission-plan-release-catalog-summary-v1",
        "catalog_id": selected_id,
        "catalog_address": catalog.content_address,
        "entry_count": catalog.entry_count,
        "accepted_entry_count": catalog.accepted_entry_count,
        "rejected_entry_count": catalog.rejected_entry_count,
        "check_count": len(checks),
        "failed_check_count": sum(not item.accepted for item in checks),
        "artifact_names": sorted(item.filename for item in artifacts),
        "accepted": catalog.accepted and all(item.accepted for item in checks),
    }
    summary_body["content_address"] = content_hash(
        {key: value for key, value in summary_body.items() if key != "content_address"},
        prefix="mission-plan-release-catalog-summary",
    )
    catalog_payloads["catalog-summary.json"] = (canonical_json(summary_body) + "\n").encode("utf-8")
    artifacts = _build_artifacts(catalog_payloads)
    artifact_metadata = [item.to_dict() for item in artifacts]
    manifest_body = {
        "manifest_version": MISSION_PLAN_RELEASE_CATALOG_VERSION,
        "catalog_id": selected_id,
        "catalog_address": catalog.content_address,
        "checks_address": checks_address,
        "summary_address": summary_body["content_address"],
        "artifact_count": len(artifacts) + 1,
        "artifacts": artifact_metadata,
        "accepted": catalog.accepted and all(item.accepted for item in checks),
    }
    manifest_body["manifest_address"] = content_hash(
        {key: value for key, value in manifest_body.items() if key != "manifest_address"},
        prefix="mission-plan-release-catalog-manifest",
    )
    manifest_payload = (canonical_json(manifest_body) + "\n").encode("utf-8")
    manifest_artifact = _artifact(
        "catalog-manifest",
        MISSION_PLAN_RELEASE_CATALOG_MANIFEST_FILE,
        "application/json",
        manifest_payload,
    )
    artifacts = tuple(sorted(artifacts + (manifest_artifact,), key=lambda item: item.filename))
    accepted = bool(manifest_body["accepted"])
    bundle_body = {
        "catalog": catalog,
        "checks": checks,
        "artifacts": tuple(item.to_dict() for item in artifacts),
        "manifest": manifest_body,
        "accepted": accepted,
    }
    return MissionPlanReleaseCatalogBundle(
        catalog=catalog,
        checks=checks,
        artifacts=artifacts,
        manifest=manifest_body,
        accepted=accepted,
        content_address=content_hash(bundle_body, prefix="mission-plan-release-catalog-bundle"),
    )


def _catalog_payloads(
    catalog: MissionPlanReleaseCatalog,
    checks: tuple[MissionPlanReleaseCatalogCheck, ...],
) -> dict[str, bytes]:
    checks_body = {
        "checks_version": "mission-plan-release-catalog-checks-v1",
        "catalog_id": catalog.catalog_id,
        "catalog_address": catalog.content_address,
        "check_count": len(checks),
        "checks": checks,
    }
    checks_address = content_hash({"checks": checks}, prefix="mission-plan-release-catalog-checks")
    checks_body["checks_address"] = checks_address
    return {
        "mission-plan-release-catalog.json": (mission_plan_release_catalog_json(catalog)).encode("utf-8"),
        "mission-plan-release-catalog.csv": mission_plan_release_catalog_csv(catalog).encode("utf-8"),
        "mission-plan-release-catalog.md": mission_plan_release_catalog_markdown(catalog).encode("utf-8"),
        "catalog-checks.json": (canonical_json(checks_body) + "\n").encode("utf-8"),
    }


def _artifact(artifact_id: str, filename: str, media_type: str, payload: bytes) -> MissionPlanReleaseCatalogArtifact:
    return MissionPlanReleaseCatalogArtifact(
        artifact_id=artifact_id,
        filename=filename,
        media_type=media_type,
        byte_count=len(payload),
        line_count=payload.count(b"\n"),
        content_address=hash_bytes(payload, prefix="mission-plan-release-catalog-artifact"),
        payload=payload,
    )


def _build_artifacts(payloads: Mapping[str, bytes]) -> tuple[MissionPlanReleaseCatalogArtifact, ...]:
    media_types = {
        "catalog-checks.json": "application/json",
        "catalog-summary.json": "application/json",
        "mission-plan-release-catalog.csv": "text/csv",
        "mission-plan-release-catalog.json": "application/json",
        "mission-plan-release-catalog.md": "text/markdown",
    }
    return tuple(
        _artifact(filename.replace(".", "-")[:-5] if filename.endswith(".json") else filename.replace(".", "-"), filename, media_types[filename], payload)
        for filename, payload in sorted(payloads.items())
    )


def write_mission_plan_release_catalog(
    value: MissionPlanReleaseCatalogBundle,
    destination: str | Path,
    *,
    allow_existing: bool = False,
) -> Path:
    """Write a catalog bundle as exact UTF-8 bytes."""

    if not isinstance(value, MissionPlanReleaseCatalogBundle):
        raise ValidationError("catalog writer requires a catalog bundle")
    root = Path(destination)
    if root.exists():
        if not root.is_dir():
            raise ValidationError("catalog destination must be a directory")
        existing = tuple(root.iterdir())
        if existing and not allow_existing:
            raise ValidationError("catalog destination is not empty")
    else:
        root.mkdir(parents=True, exist_ok=False)
    for artifact in value.artifacts:
        (root / artifact.filename).write_bytes(artifact.payload)
    return root


def verify_mission_plan_release_catalog(destination: str | Path) -> MissionPlanReleaseCatalogVerification:
    """Verify catalog names, bytes, addresses, and public-boundary safety."""

    root = Path(destination)
    if not root.exists() or not root.is_dir():
        raise ValidationError("catalog destination must be an existing directory")
    files = tuple(sorted(item.name for item in root.iterdir() if item.is_file()))
    missing = tuple(sorted(MISSION_PLAN_RELEASE_CATALOG_REQUIRED_ARTIFACTS - set(files)))
    unexpected = tuple(sorted(set(files) - MISSION_PLAN_RELEASE_CATALOG_REQUIRED_ARTIFACTS))
    tampered: list[str] = []
    artifact_count = 0
    verified_count = 0
    catalog_id = "unknown"
    manifest_address_valid = catalog_address_valid = checks_address_valid = summary_address_valid = False
    public_boundary_valid = True
    exact_bytes = not missing and not unexpected
    manifest_body: dict[str, Any] = {}
    try:
        manifest_body = json.loads((root / MISSION_PLAN_RELEASE_CATALOG_MANIFEST_FILE).read_text(encoding="utf-8"))
        catalog_id = _text(manifest_body.get("catalog_id"), "manifest.catalog_id", maximum=96)
        if _private_key_paths(manifest_body):
            public_boundary_valid = False
        declared_manifest_address = manifest_body.get("manifest_address")
        reconstructed_manifest = content_hash(
            {key: value for key, value in manifest_body.items() if key != "manifest_address"},
            prefix="mission-plan-release-catalog-manifest",
        )
        manifest_address_valid = declared_manifest_address == reconstructed_manifest
        metadata = {item["filename"]: item for item in manifest_body.get("artifacts", ())}
        artifact_count = int(manifest_body.get("artifact_count", 0))
        for filename in sorted(MISSION_PLAN_RELEASE_CATALOG_REQUIRED_ARTIFACTS - {MISSION_PLAN_RELEASE_CATALOG_MANIFEST_FILE}):
            path = root / filename
            if not path.exists():
                continue
            payload = path.read_bytes()
            item = metadata.get(filename)
            if not isinstance(item, Mapping):
                tampered.append(filename)
                continue
            expected = item.get("content_address")
            actual = hash_bytes(payload, prefix="mission-plan-release-catalog-artifact")
            if expected != actual or item.get("byte_count") != len(payload):
                tampered.append(filename)
            else:
                verified_count += 1
            if _private_key_paths(json.loads(payload.decode("utf-8"))) if filename.endswith(".json") else False:
                public_boundary_valid = False
        if (root / "mission-plan-release-catalog.json").exists():
            catalog_payload = json.loads((root / "mission-plan-release-catalog.json").read_text(encoding="utf-8"))
            catalog = MissionPlanReleaseCatalog.from_mapping(catalog_payload)
            catalog_address_valid = catalog.content_address == manifest_body.get("catalog_address")
        if (root / "catalog-checks.json").exists():
            checks_payload = json.loads((root / "catalog-checks.json").read_text(encoding="utf-8"))
            checks = tuple(MissionPlanReleaseCatalogCheck.from_mapping(item) for item in checks_payload.get("checks", ()))
            checks_address_valid = checks_payload.get("checks_address") == content_hash(
                {"checks": checks}, prefix="mission-plan-release-catalog-checks"
            ) and checks_payload.get("checks_address") == manifest_body.get("checks_address")
        if (root / "catalog-summary.json").exists():
            summary = json.loads((root / "catalog-summary.json").read_text(encoding="utf-8"))
            summary_address = summary.get("content_address")
            summary_address_valid = summary_address == content_hash(
                {key: value for key, value in summary.items() if key != "content_address"},
                prefix="mission-plan-release-catalog-summary",
            ) and summary_address == manifest_body.get("summary_address")
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError, ValidationError):
        exact_bytes = False
        if MISSION_PLAN_RELEASE_CATALOG_MANIFEST_FILE not in tampered:
            tampered.append(MISSION_PLAN_RELEASE_CATALOG_MANIFEST_FILE)
    tampered = sorted(set(tampered))
    accepted = bool(
        manifest_address_valid
        and catalog_address_valid
        and checks_address_valid
        and summary_address_valid
        and exact_bytes
        and public_boundary_valid
        and not tampered
        and artifact_count == len(MISSION_PLAN_RELEASE_CATALOG_REQUIRED_ARTIFACTS)
        and verified_count == len(MISSION_PLAN_RELEASE_CATALOG_REQUIRED_ARTIFACTS) - 1
    )
    body = {
        "catalog_id": catalog_id,
        "accepted": accepted,
        "manifest_address_valid": manifest_address_valid,
        "catalog_address_valid": catalog_address_valid,
        "checks_address_valid": checks_address_valid,
        "summary_address_valid": summary_address_valid,
        "artifact_set_valid": not missing and not unexpected,
        "exact_bytes": exact_bytes,
        "public_boundary_valid": public_boundary_valid,
        "missing_files": missing,
        "unexpected_files": unexpected,
        "tampered_files": tuple(tampered),
        "artifact_count": artifact_count,
        "verified_artifact_count": verified_count,
    }
    return MissionPlanReleaseCatalogVerification(
        **body,
        content_address=content_hash(body, prefix="mission-plan-release-catalog-verification"),
    )


def load_mission_plan_release_catalog(destination: str | Path) -> MissionPlanReleaseCatalogOffline:
    """Verify and hydrate a catalog without its original builder."""

    verification = verify_mission_plan_release_catalog(destination)
    if not verification.accepted:
        raise ValidationError("catalog verification failed: " + canonical_json(verification.to_dict()))
    root = Path(destination)
    manifest = json.loads((root / MISSION_PLAN_RELEASE_CATALOG_MANIFEST_FILE).read_text(encoding="utf-8"))
    catalog = MissionPlanReleaseCatalog.from_mapping(
        json.loads((root / "mission-plan-release-catalog.json").read_text(encoding="utf-8"))
    )
    checks_payload = json.loads((root / "catalog-checks.json").read_text(encoding="utf-8"))
    checks = tuple(MissionPlanReleaseCatalogCheck.from_mapping(item) for item in checks_payload["checks"])
    body = {
        "catalog": catalog,
        "checks": checks,
        "manifest": manifest,
        "accepted": True,
    }
    return MissionPlanReleaseCatalogOffline(
        **body,
        content_address=content_hash(body, prefix="mission-plan-release-catalog-offline"),
    )


def mission_plan_release_catalog_json(value: MissionPlanReleaseCatalog) -> str:
    """Render catalog entries as canonical JSON."""

    return canonical_json(value.to_dict()) + "\n"


def mission_plan_release_catalog_csv(value: MissionPlanReleaseCatalog) -> str:
    """Render one deterministic row per release."""

    output = StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        (
            "release_id",
            "release_address",
            "plan_id",
            "plan_address",
            "state",
            "decision",
            "accepted",
            "step_count",
            "optional_step_count",
            "deterministic_step_count",
            "network_step_count",
            "artifact_count",
            "check_count",
            "warning_count",
            "workflow_kinds",
            "content_address",
        )
    )
    for item in value.entries:
        writer.writerow(
            (
                item.release_id,
                item.release_address,
                item.plan_id,
                item.plan_address,
                item.state,
                item.decision,
                item.accepted,
                item.step_count,
                item.optional_step_count,
                item.deterministic_step_count,
                item.network_step_count,
                item.artifact_count,
                item.check_count,
                item.warning_count,
                "|".join(item.workflow_kinds),
                item.content_address,
            )
        )
    return output.getvalue()


def mission_plan_release_catalog_markdown(value: MissionPlanReleaseCatalog) -> str:
    """Render a review-safe catalog table."""

    lines = [
        "# Mission plan release catalog",
        "",
        f"- Catalog: `{value.catalog_id}`",
        f"- Entries: `{value.entry_count}`",
        f"- Accepted entries: `{value.accepted_entry_count}`",
        f"- Accepted: `{value.accepted}`",
        "",
        "| Release | Plan | State | Accepted | Steps | Warnings |",
        "| --- | --- | --- | --- | ---: | ---: |",
    ]
    lines.extend(
        f"| `{item.release_id}` | `{item.plan_id}` | `{item.state}` | `{item.accepted}` | "
        f"{item.step_count} | {item.warning_count} |"
        for item in value.entries
    )
    return "\n".join(lines) + "\n"


def mission_plan_release_catalog_export_payloads(
    value: MissionPlanReleaseCatalog,
) -> dict[str, str]:
    """Return deterministic catalog projections."""

    return {
        "mission-plan-release-catalog.json": mission_plan_release_catalog_json(value),
        "mission-plan-release-catalog.csv": mission_plan_release_catalog_csv(value),
        "mission-plan-release-catalog.md": mission_plan_release_catalog_markdown(value),
    }


def mission_plan_release_catalog_schema() -> dict[str, Any]:
    """Return the closed catalog contract."""

    return {
        "version": MISSION_PLAN_RELEASE_CATALOG_SCHEMA_VERSION,
        "catalog_version": MISSION_PLAN_RELEASE_CATALOG_VERSION,
        "required_files": sorted(MISSION_PLAN_RELEASE_CATALOG_REQUIRED_ARTIFACTS),
        "entry_fields": [
            "release_id",
            "release_address",
            "plan_id",
            "plan_address",
            "state",
            "decision",
            "accepted",
            "step_count",
            "optional_step_count",
            "deterministic_step_count",
            "network_step_count",
            "artifact_count",
            "check_count",
            "warning_count",
            "workflow_kinds",
            "content_address",
        ],
        "max_entries": MISSION_PLAN_RELEASE_CATALOG_MAX_ENTRIES,
        "max_artifacts": MISSION_PLAN_RELEASE_CATALOG_MAX_ARTIFACTS,
        "max_checks": MISSION_PLAN_RELEASE_CATALOG_MAX_CHECKS,
        "ordering": ["release_id", "plan_address"],
        "timestamp_free": True,
        "boundary": {
            "routing_metadata": False,
            "producer_metadata": False,
            "model_metadata": False,
            "programming_language_metadata": False,
            "raw_request_payload": False,
        },
    }


def mission_plan_release_catalog_capabilities() -> dict[str, Any]:
    """Return catalog capabilities."""

    return {
        "version": MISSION_PLAN_RELEASE_CATALOG_CAPABILITIES_VERSION,
        "multi_release_inventory": True,
        "canonical_ordering": True,
        "identity_collision_checks": True,
        "exact_byte_materialization": True,
        "independent_filesystem_verification": True,
        "offline_hydration": True,
        "public_boundary_audit": True,
        "json_export": True,
        "markdown_export": True,
        "csv_export": True,
        "read_only": True,
        "timestamp_free": True,
        "execution_authorization": False,
    }


__all__ = [
    "MISSION_PLAN_RELEASE_CATALOG_CAPABILITIES_VERSION",
    "MISSION_PLAN_RELEASE_CATALOG_MANIFEST_FILE",
    "MISSION_PLAN_RELEASE_CATALOG_MAX_ARTIFACTS",
    "MISSION_PLAN_RELEASE_CATALOG_MAX_CHECKS",
    "MISSION_PLAN_RELEASE_CATALOG_MAX_ENTRIES",
    "MISSION_PLAN_RELEASE_CATALOG_REQUIRED_ARTIFACTS",
    "MISSION_PLAN_RELEASE_CATALOG_SCHEMA_VERSION",
    "MISSION_PLAN_RELEASE_CATALOG_VERSION",
    "MissionPlanReleaseCatalog",
    "MissionPlanReleaseCatalogArtifact",
    "MissionPlanReleaseCatalogBundle",
    "MissionPlanReleaseCatalogCheck",
    "MissionPlanReleaseCatalogEntry",
    "MissionPlanReleaseCatalogOffline",
    "MissionPlanReleaseCatalogVerification",
    "build_mission_plan_release_catalog",
    "load_mission_plan_release_catalog",
    "mission_plan_release_catalog_capabilities",
    "mission_plan_release_catalog_csv",
    "mission_plan_release_catalog_export_payloads",
    "mission_plan_release_catalog_json",
    "mission_plan_release_catalog_markdown",
    "mission_plan_release_catalog_schema",
    "verify_mission_plan_release_catalog",
    "write_mission_plan_release_catalog",
]
