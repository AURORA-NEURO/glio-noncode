"""Durable runtime handoffs for archive-transfer recovery execution receipts."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
import json
import os
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution as execution_model
from .errors import ValidationError
from .serialization import canonical_bytes, canonical_json, content_hash, hash_bytes

VERSION = execution_model.VERSION + "-runtime-v1"
BOUNDARY = execution_model.BOUNDARY + "_runtime"
RUNTIME_PREFIX = execution_model.EXECUTION_PREFIX + "-runtime"
STAGE_PREFIX = RUNTIME_PREFIX + "-stage"
ARTIFACT_PREFIX = RUNTIME_PREFIX + "-artifact"
MANIFEST_PREFIX = RUNTIME_PREFIX + "-manifest"
DEFAULT_RUNTIME_ID = "comparison-query-snapshot-registry-history-observatory-archive-transfer-recovery-execution-runtime"
FILES = ("manifest.json", "runtime.json", "execution.json", "execution-audit.json", "execution-query.json", "execution-query-audit.json", "summary.json")
ARTIFACT_FILES = FILES[1:]
STAGES = ("execution", "audit", "query", "query-audit", "complete")
STATES = ("ready", "blocked")
MAX_RUNTIME_BYTES = 16 * 1024 * 1024
STAGE_FIELDS = ("ordinal", "stage", "state", "accepted", "address", "detail", "content_address")
ARTIFACT_FIELDS = ("ordinal", "name", "size", "hash", "content_address")
MANIFEST_FIELDS = ("runtime_id", "version", "boundary", "files", "artifacts", "runtime_address", "manifest_address")
RUNTIME_FIELDS = ("runtime_id", "version", "boundary", "execution_id", "execution_address", "execution_audit_address", "query_address", "query_audit_address", "stage_count", "stages", "state", "accepted", "content_address")
MANIFEST_ARTIFACT_FIELDS = ARTIFACT_FIELDS


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 512)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, allow_pending: bool = False) -> str:
    value = _text(value, field)
    if allow_pending and value.startswith("pending:"):
        return value
    if ":" not in value or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a public address")
    if prefix is not None and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has the wrong address namespace")
    return value


def _count(value: Any, field: str, maximum: int, *, lower: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < lower or value > maximum:
        raise ValidationError(f"{field} is outside its bound")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded array")
    return tuple(value)


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return value


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    return execution_model._public(value)


class RecoveryExecutionRuntimeStage:
    """One deterministic stage in a recovery execution runtime."""

    FIELDS = STAGE_FIELDS

    def __init__(self, ordinal: int, stage: str, state: str, accepted: bool, address: str, detail: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "runtime stage ordinal", len(STAGES), lower=1)
        if stage not in STAGES:
            raise ValidationError("runtime stage is unsupported")
        self.stage = stage
        if state not in STATES:
            raise ValidationError("runtime stage state is unsupported")
        self.state = state
        self.accepted = _bool(accepted, "runtime stage acceptance")
        self.address = _address(address, "runtime stage address")
        self.detail = _text(detail, "runtime stage detail", 1024)
        self.content_address = _address(content_address, "runtime stage content address", STAGE_PREFIX, allow_pending=True)
        if self.accepted != (self.state == "ready"):
            raise ValidationError("runtime stage state does not replay acceptance")
        if not self.content_address.startswith("pending:") and address_stage(self) != self.content_address:
            raise ValidationError("runtime stage content address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RecoveryExecutionRuntimeStage:
        value = _mapping(value, "runtime stage")
        _strict(value, set(cls.FIELDS), "runtime stage")
        return cls(*(value[field] for field in cls.FIELDS))


class RecoveryExecutionRuntimeArtifact:
    """A byte receipt for one persisted runtime document."""

    FIELDS = ARTIFACT_FIELDS

    def __init__(self, ordinal: int, name: str, size: int, hash: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "runtime artifact ordinal", len(ARTIFACT_FILES), lower=1)
        if name not in ARTIFACT_FILES:
            raise ValidationError("runtime artifact name is unsupported")
        self.name = name
        self.size = _count(size, "runtime artifact size", MAX_RUNTIME_BYTES, lower=1)
        self.hash = _address(hash, "runtime artifact hash", ARTIFACT_PREFIX)
        self.content_address = _address(content_address, "runtime artifact content address", ARTIFACT_PREFIX, allow_pending=True)
        if not self.content_address.startswith("pending:") and address_artifact(self) != self.content_address:
            raise ValidationError("runtime artifact content address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RecoveryExecutionRuntimeArtifact:
        value = _mapping(value, "runtime artifact")
        _strict(value, set(cls.FIELDS), "runtime artifact")
        return cls(*(value[field] for field in cls.FIELDS))


class RecoveryExecutionRuntimeManifest:
    """The exact-file manifest for a persisted execution runtime."""

    FIELDS = MANIFEST_FIELDS

    def __init__(self, runtime_id: str, version: str, boundary: str, files: Sequence[str], artifacts: Sequence[RecoveryExecutionRuntimeArtifact], runtime_address: str, manifest_address: str) -> None:
        self.runtime_id = _label(runtime_id, "runtime manifest ID")
        self.version = _text(version, "runtime manifest version", 2048)
        self.boundary = _text(boundary, "runtime manifest boundary", 1024)
        if tuple(files) != FILES:
            raise ValidationError("runtime manifest files are not canonical")
        self.files = tuple(files)
        self.artifacts = tuple(item if isinstance(item, RecoveryExecutionRuntimeArtifact) else RecoveryExecutionRuntimeArtifact.from_mapping(item) for item in _sequence(artifacts, "runtime manifest artifacts", len(ARTIFACT_FILES)))
        if tuple(item.ordinal for item in self.artifacts) != tuple(range(1, len(ARTIFACT_FILES) + 1)) or tuple(item.name for item in self.artifacts) != ARTIFACT_FILES:
            raise ValidationError("runtime manifest artifacts are not ordered")
        self.runtime_address = _address(runtime_address, "runtime manifest runtime address", RUNTIME_PREFIX)
        self.manifest_address = _address(manifest_address, "runtime manifest address", MANIFEST_PREFIX, allow_pending=True)
        if not self.manifest_address.startswith("pending:") and address_manifest(self) != self.manifest_address:
            raise ValidationError("runtime manifest address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"runtime_id": self.runtime_id, "version": self.version, "boundary": self.boundary, "files": self.files, "artifacts": [item.to_dict() for item in self.artifacts], "runtime_address": self.runtime_address, "manifest_address": self.manifest_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RecoveryExecutionRuntimeManifest:
        value = _mapping(value, "runtime manifest")
        _strict(value, set(cls.FIELDS), "runtime manifest")
        return cls(value["runtime_id"], value["version"], value["boundary"], value["files"], tuple(RecoveryExecutionRuntimeArtifact.from_mapping(item) for item in _sequence(value["artifacts"], "runtime manifest artifacts", len(ARTIFACT_FILES))), value["runtime_address"], value["manifest_address"])


class RecoveryExecutionRuntime:
    """A durable, value-free handoff for execution and its inspections."""

    FIELDS = RUNTIME_FIELDS

    def __init__(self, runtime_id: str, version: str, boundary: str, execution_id: str, execution_address: str, execution_audit_address: str, query_address: str, query_audit_address: str, stage_count: int, stages: Sequence[RecoveryExecutionRuntimeStage], state: str, accepted: bool, content_address: str, *, execution: Any = None, execution_audit: Any = None, query: Any = None, query_audit: Any = None) -> None:
        self.runtime_id = _label(runtime_id, "runtime ID")
        self.version = _text(version, "runtime version", 2048)
        self.boundary = _text(boundary, "runtime boundary", 1024)
        self.execution_id = _label(execution_id, "runtime execution ID")
        self.execution_address = _address(execution_address, "runtime execution address", execution_model.EXECUTION_PREFIX)
        self.execution_audit_address = _address(execution_audit_address, "runtime execution audit address")
        self.query_address = _address(query_address, "runtime query address")
        self.query_audit_address = _address(query_audit_address, "runtime query audit address")
        self.stage_count = _count(stage_count, "runtime stage count", len(STAGES))
        self.stages = tuple(item if isinstance(item, RecoveryExecutionRuntimeStage) else RecoveryExecutionRuntimeStage.from_mapping(item) for item in _sequence(stages, "runtime stages", len(STAGES)))
        if state not in STATES:
            raise ValidationError("runtime state is unsupported")
        self.state = state
        self.accepted = _bool(accepted, "runtime acceptance")
        self.content_address = _address(content_address, "runtime content address", RUNTIME_PREFIX, allow_pending=True)
        self.execution = execution
        self.execution_audit = execution_audit
        self.query = query
        self.query_audit = query_audit
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("runtime version or boundary is not current")
        if self.stage_count != len(STAGES) or tuple(item.ordinal for item in self.stages) != tuple(range(1, len(STAGES) + 1)) or tuple(item.stage for item in self.stages) != STAGES:
            raise ValidationError("runtime stages are not canonical")
        if self.state != ("ready" if self.accepted else "blocked"):
            raise ValidationError("runtime state does not replay acceptance")
        if not _public(self.to_dict()):
            raise ValidationError("runtime crosses the public boundary")
        if not self.content_address.startswith("pending:") and address_runtime(self) != self.content_address:
            raise ValidationError("runtime content address does not replay")
        if self.execution is not None:
            if not isinstance(self.execution, execution_model.RecoveryExecution) or self.execution.execution_id != self.execution_id or self.execution.content_address != self.execution_address:
                raise ValidationError("runtime execution linkage does not replay")
            if self.execution_audit is None or self.query is None or self.query_audit is None:
                raise ValidationError("runtime composed receipts are incomplete")
            if self.execution_audit.content_address != self.execution_audit_address or self.query.content_address != self.query_address or self.query_audit.content_address != self.query_audit_address:
                raise ValidationError("runtime component addresses do not replay")
            expected = _build_stages(self, self.execution_audit, self.query, self.query_audit)
            if tuple(item.to_dict() for item in self.stages) != tuple(item.to_dict() for item in expected):
                raise ValidationError("runtime stages do not replay components")
            if self.accepted != (self.execution_audit.passed and self.query_audit.passed):
                raise ValidationError("runtime acceptance does not replay component audits")

    def to_dict(self) -> dict[str, Any]:
        return {"runtime_id": self.runtime_id, "version": self.version, "boundary": self.boundary, "execution_id": self.execution_id, "execution_address": self.execution_address, "execution_audit_address": self.execution_audit_address, "query_address": self.query_address, "query_audit_address": self.query_audit_address, "stage_count": self.stage_count, "stages": [item.to_dict() for item in self.stages], "state": self.state, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field not in {"stages"}}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RecoveryExecutionRuntime:
        value = _mapping(value, "recovery execution runtime")
        _strict(value, set(cls.FIELDS), "recovery execution runtime")
        return cls(value["runtime_id"], value["version"], value["boundary"], value["execution_id"], value["execution_address"], value["execution_audit_address"], value["query_address"], value["query_audit_address"], value["stage_count"], tuple(RecoveryExecutionRuntimeStage.from_mapping(item) for item in _sequence(value["stages"], "runtime stages", len(STAGES))), value["state"], value["accepted"], value["content_address"])


def address_stage(value: RecoveryExecutionRuntimeStage) -> str:
    if not isinstance(value, RecoveryExecutionRuntimeStage):
        raise ValidationError("runtime stage address requires a typed stage")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=STAGE_PREFIX)


def address_artifact(value: RecoveryExecutionRuntimeArtifact) -> str:
    if not isinstance(value, RecoveryExecutionRuntimeArtifact):
        raise ValidationError("runtime artifact address requires a typed artifact")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ARTIFACT_PREFIX)


def address_manifest(value: RecoveryExecutionRuntimeManifest) -> str:
    if not isinstance(value, RecoveryExecutionRuntimeManifest):
        raise ValidationError("runtime manifest address requires a typed manifest")
    return content_hash(value.to_dict() | {"manifest_address": None}, prefix=MANIFEST_PREFIX)


def address_runtime(value: RecoveryExecutionRuntime) -> str:
    if not isinstance(value, RecoveryExecutionRuntime):
        raise ValidationError("runtime address requires a typed runtime")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=RUNTIME_PREFIX)


def _stage(ordinal: int, stage: str, accepted: bool, address: str, detail: str) -> RecoveryExecutionRuntimeStage:
    pending = RecoveryExecutionRuntimeStage(ordinal, stage, "ready" if accepted else "blocked", accepted, address, detail, "pending:runtime-stage")
    return RecoveryExecutionRuntimeStage(ordinal, stage, pending.state, accepted, address, detail, address_stage(pending))


def _build_stages(value: RecoveryExecutionRuntime, execution_audit: Any, query: Any, query_audit: Any) -> tuple[RecoveryExecutionRuntimeStage, ...]:
    return (
        _stage(1, "execution", True, value.execution_address, "execution receipt is structurally valid"),
        _stage(2, "audit", execution_audit.passed, value.execution_audit_address, "independent execution audit completed"),
        _stage(3, "query", True, value.query_address, "bounded execution query completed"),
        _stage(4, "query-audit", query_audit.passed, value.query_audit_address, "independent execution query audit completed"),
        _stage(5, "complete", execution_audit.passed and query_audit.passed, value.query_audit_address, "runtime handoff is ready" if execution_audit.passed and query_audit.passed else "runtime handoff is blocked by an audit result"),
    )


def build_runtime(execution: execution_model.RecoveryExecution, *, runtime_id: str = DEFAULT_RUNTIME_ID, resources: Sequence[str] | None = None, status: str = "", index: int = -1, text: str = "", offset: int = 0, limit: int | None = None) -> RecoveryExecutionRuntime:
    from . import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution_audit as execution_audit_model
    from . import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution_query as query_model
    from . import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution_query_audit as query_audit_model

    execution = execution_model.execution_from_mapping(execution.to_dict()) if isinstance(execution, execution_model.RecoveryExecution) else execution_model.execution_from_mapping(execution)
    execution_audit = execution_audit_model.audit_execution(execution)
    query_kwargs: dict[str, Any] = {"resources": resources, "status": status, "index": index, "text": text}
    if limit is not None:
        query_kwargs["limit"] = limit
    query = query_model.query_execution(execution, **query_kwargs)
    query_audit = query_audit_model.audit_query(query, execution)
    accepted = execution_audit.passed and query_audit.passed
    body = {"runtime_id": runtime_id, "version": VERSION, "boundary": BOUNDARY, "execution_id": execution.execution_id, "execution_address": execution.content_address, "execution_audit_address": execution_audit.content_address, "query_address": query.content_address, "query_audit_address": query_audit.content_address, "stage_count": len(STAGES), "state": "ready" if accepted else "blocked", "accepted": accepted}
    provisional = RecoveryExecutionRuntime(**body, stages=(_stage(1, "execution", True, execution.content_address, "execution receipt is structurally valid"), _stage(2, "audit", execution_audit.passed, execution_audit.content_address, "independent execution audit completed"), _stage(3, "query", True, query.content_address, "bounded execution query completed"), _stage(4, "query-audit", query_audit.passed, query_audit.content_address, "independent execution query audit completed"), _stage(5, "complete", accepted, query_audit.content_address, "runtime handoff is ready" if accepted else "runtime handoff is blocked by an audit result")), content_address="pending:runtime", execution=execution, execution_audit=execution_audit, query=query, query_audit=query_audit)
    stages = _build_stages(provisional, execution_audit, query, query_audit)
    provisional = RecoveryExecutionRuntime(**body, stages=stages, content_address="pending:runtime", execution=execution, execution_audit=execution_audit, query=query, query_audit=query_audit)
    return RecoveryExecutionRuntime(**body, stages=stages, content_address=address_runtime(provisional), execution=execution, execution_audit=execution_audit, query=query, query_audit=query_audit)


def verify_runtime(value: RecoveryExecutionRuntime) -> RecoveryExecutionRuntime:
    if not isinstance(value, RecoveryExecutionRuntime):
        raise ValidationError("runtime verification requires a typed runtime")
    value._validate()
    if not value.content_address.startswith("pending:") and address_runtime(value) != value.content_address:
        raise ValidationError("runtime address verification failed")
    return value


def runtime_from_mapping(value: Mapping[str, Any]) -> RecoveryExecutionRuntime:
    return RecoveryExecutionRuntime.from_mapping(value)


def runtime_json(value: RecoveryExecutionRuntime) -> str:
    return canonical_json(runtime_from_mapping(value.to_dict()).to_dict())


def runtime_csv(value: RecoveryExecutionRuntime) -> str:
    value = verify_runtime(value)
    stream = io.StringIO(newline="")
    fields = ("runtime_id", "execution_id", "execution_address", "execution_audit_address", "query_address", "query_audit_address", "stage_count", "state", "accepted", "content_address")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerow({field: value.to_dict()[field] for field in fields})
    return stream.getvalue()


def render_runtime_markdown(value: RecoveryExecutionRuntime) -> str:
    value = verify_runtime(value)
    lines = ["# Archive transfer recovery execution runtime", "", f"- Runtime: `{value.runtime_id}`", f"- Execution: `{value.execution_id}`", f"- State: `{value.state}`", f"- Accepted: `{value.accepted}`", f"- Address: `{value.content_address}`", "", "| # | stage | state | accepted | address |", "| ---: | --- | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.stage}` | `{item.state}` | `{item.accepted}` | `{item.address}` |" for item in value.stages)
    return "\n".join(lines) + "\n"


def _documents(value: RecoveryExecutionRuntime) -> dict[str, bytes]:
    if any(item is None for item in (value.execution, value.execution_audit, value.query, value.query_audit)):
        raise ValidationError("runtime persistence requires composed receipts")
    return {"runtime.json": canonical_bytes(value.to_dict()), "execution.json": canonical_bytes(value.execution.to_dict()), "execution-audit.json": canonical_bytes(value.execution_audit.to_dict()), "execution-query.json": canonical_bytes(value.query.to_dict()), "execution-query-audit.json": canonical_bytes(value.query_audit.to_dict()), "summary.json": canonical_bytes(value.summary())}


def _build_manifest(value: RecoveryExecutionRuntime) -> RecoveryExecutionRuntimeManifest:
    documents = _documents(value)
    receipts = tuple(RecoveryExecutionRuntimeArtifact(index, name, len(documents[name]), hash_bytes(documents[name], prefix=ARTIFACT_PREFIX), "pending:runtime-artifact") for index, name in enumerate(ARTIFACT_FILES, 1))
    receipts = tuple(RecoveryExecutionRuntimeArtifact(item.ordinal, item.name, item.size, item.hash, address_artifact(item)) for item in receipts)
    body = {"runtime_id": value.runtime_id, "version": VERSION, "boundary": BOUNDARY, "files": FILES, "artifacts": receipts, "runtime_address": value.content_address}
    provisional = RecoveryExecutionRuntimeManifest(**body, manifest_address="pending:runtime-manifest")
    return RecoveryExecutionRuntimeManifest(**body, manifest_address=address_manifest(provisional))


def manifest_document(value: RecoveryExecutionRuntime) -> dict[str, Any]:
    return _build_manifest(verify_runtime(value)).to_dict()


def manifest_schema() -> dict[str, Any]:
    artifact = {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Recovery execution runtime artifact", "type": "object", "additionalProperties": False, "required": list(ARTIFACT_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "name": {"type": "string", "enum": list(ARTIFACT_FILES)}, "size": {"type": "integer", "minimum": 1}, "hash": {"type": "string", "pattern": "^" + ARTIFACT_PREFIX + ":"}, "content_address": {"type": "string", "pattern": "^" + ARTIFACT_PREFIX + ":"}}}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Recovery execution runtime manifest", "type": "object", "additionalProperties": False, "required": list(MANIFEST_FIELDS), "properties": {"runtime_id": {"type": "string"}, "version": {"type": "string", "const": VERSION}, "boundary": {"type": "string", "const": BOUNDARY}, "files": {"const": list(FILES)}, "artifacts": {"type": "array", "items": artifact, "minItems": len(ARTIFACT_FILES), "maxItems": len(ARTIFACT_FILES)}, "runtime_address": {"type": "string", "pattern": "^" + RUNTIME_PREFIX + ":"}, "manifest_address": {"type": "string", "pattern": "^" + MANIFEST_PREFIX + ":"}}}


def stage_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Recovery execution runtime stage", "type": "object", "additionalProperties": False, "required": list(STAGE_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1, "maximum": len(STAGES)}, "stage": {"type": "string", "enum": list(STAGES)}, "state": {"type": "string", "enum": list(STATES)}, "accepted": {"type": "boolean"}, "address": {"type": "string"}, "detail": {"type": "string"}, "content_address": {"type": "string", "pattern": "^" + STAGE_PREFIX + ":"}}}


def runtime_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Archive transfer recovery execution runtime", "type": "object", "additionalProperties": False, "required": list(RUNTIME_FIELDS), "properties": {"runtime_id": {"type": "string"}, "version": {"type": "string", "const": VERSION}, "boundary": {"type": "string", "const": BOUNDARY}, "execution_id": {"type": "string"}, "execution_address": {"type": "string", "pattern": "^" + execution_model.EXECUTION_PREFIX + ":"}, "execution_audit_address": {"type": "string"}, "query_address": {"type": "string"}, "query_audit_address": {"type": "string"}, "stage_count": {"type": "integer", "const": len(STAGES)}, "stages": {"type": "array", "items": stage_schema(), "minItems": len(STAGES), "maxItems": len(STAGES)}, "state": {"type": "string", "enum": list(STATES)}, "accepted": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + RUNTIME_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "runtime_prefix": RUNTIME_PREFIX, "stage_prefix": STAGE_PREFIX, "manifest_prefix": MANIFEST_PREFIX, "files": FILES, "artifacts": ARTIFACT_FILES, "stages": STAGES, "states": STATES, "operations": ("build_runtime", "runtime_from_mapping", "runtime_json", "runtime_csv", "render_runtime_markdown", "manifest_document", "persist_runtime", "load_runtime", "run_runtime"), "limits": {"max_runtime_bytes": MAX_RUNTIME_BYTES}}


def _write(path: Path, raw: bytes) -> None:
    path.write_bytes(raw)


def persist_runtime(value: RecoveryExecutionRuntime, destination: str | Path, *, overwrite: bool = False) -> Path:
    value = verify_runtime(value)
    documents = _documents(value)
    manifest = _build_manifest(value)
    members = {"manifest.json": canonical_bytes(manifest.to_dict()), **documents}
    target = Path(destination)
    if target.exists():
        if not overwrite:
            raise ValidationError("runtime destination exists; explicit overwrite is required")
        if target.is_symlink() or not target.is_dir():
            raise ValidationError("runtime destination must be a regular directory")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=target.name + ".", dir=target.parent))
    try:
        for filename in FILES:
            _write(temporary / filename, members[filename])
        if target.exists():
            shutil.rmtree(target)
        os.replace(temporary, target)
    except OSError as error:
        shutil.rmtree(temporary, ignore_errors=True)
        raise ValidationError("runtime could not be persisted atomically") from error
    return target


def _read_json(path: Path) -> tuple[Mapping[str, Any], bytes]:
    try:
        raw = path.read_bytes()
        value = _mapping(json.loads(raw.decode("utf-8")), f"runtime member {path.name}")
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationError(f"runtime member {path.name} is not valid JSON") from error
    if canonical_bytes(value) != raw:
        raise ValidationError(f"runtime member {path.name} is not canonical")
    return value, raw


def _compose(runtime: RecoveryExecutionRuntime, execution: Any, execution_audit: Any, query: Any, query_audit: Any) -> RecoveryExecutionRuntime:
    body = runtime.to_dict()
    return RecoveryExecutionRuntime(**body, execution=execution, execution_audit=execution_audit, query=query, query_audit=query_audit)


def load_runtime(destination: str | Path) -> RecoveryExecutionRuntime:
    from . import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution_audit as execution_audit_model
    from . import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution_query as query_model
    from . import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_transfer_recovery_execution_query_audit as query_audit_model

    root = Path(destination)
    if root.is_symlink() or not root.is_dir():
        raise ValidationError("runtime source must be a regular directory")
    entries = tuple(root.iterdir())
    if tuple(sorted(item.name for item in entries)) != tuple(sorted(FILES)) or any(item.is_symlink() or not item.is_file() for item in entries):
        raise ValidationError("runtime directory has an unexpected file set")
    manifest_raw, manifest_bytes = _read_json(root / "manifest.json")
    manifest = RecoveryExecutionRuntimeManifest.from_mapping(manifest_raw)
    runtime_raw, _ = _read_json(root / "runtime.json")
    runtime = runtime_from_mapping(runtime_raw)
    execution_raw, _ = _read_json(root / "execution.json")
    execution = execution_model.execution_from_mapping(execution_raw)
    execution_audit_raw, _ = _read_json(root / "execution-audit.json")
    execution_audit = execution_audit_model.audit_from_mapping(execution_audit_raw)
    query_raw, _ = _read_json(root / "execution-query.json")
    query = query_model.query_from_mapping(query_raw)
    query_audit_raw, _ = _read_json(root / "execution-query-audit.json")
    query_audit = query_audit_model.audit_from_mapping(query_audit_raw)
    candidate = _compose(runtime, execution, execution_audit, query, query_audit)
    expected_manifest = _build_manifest(candidate)
    if manifest.to_dict() != expected_manifest.to_dict() or manifest_bytes != canonical_bytes(expected_manifest.to_dict()):
        raise ValidationError("runtime manifest does not replay")
    documents = _documents(candidate)
    expected_members = {"manifest.json": canonical_bytes(expected_manifest.to_dict()), **documents}
    for filename in FILES:
        if (root / filename).read_bytes() != expected_members[filename]:
            raise ValidationError(f"runtime member {filename} does not replay")
    for receipt in manifest.artifacts:
        raw = expected_members[receipt.name]
        expected = RecoveryExecutionRuntimeArtifact(receipt.ordinal, receipt.name, len(raw), hash_bytes(raw, prefix=ARTIFACT_PREFIX), "pending:runtime-artifact")
        if receipt.size != expected.size or receipt.hash != expected.hash or receipt.content_address != address_artifact(expected):
            raise ValidationError("runtime artifact receipt does not replay")
    return verify_runtime(candidate)


def run_runtime(source: str | Path | RecoveryExecutionRuntime | execution_model.RecoveryExecution, *, runtime_id: str = DEFAULT_RUNTIME_ID, resources: Sequence[str] | None = None, status: str = "", index: int = -1, text: str = "", offset: int = 0, limit: int | None = None, destination: str | Path | None = None, overwrite: bool = False) -> RecoveryExecutionRuntime:
    if isinstance(source, (str, Path)):
        path = Path(source)
        if path.is_dir() and tuple(sorted(item.name for item in path.iterdir())) == tuple(sorted(FILES)):
            value = load_runtime(path)
        else:
            raw, _ = _read_json(path)
            value = build_runtime(execution_model.execution_from_mapping(raw), runtime_id=runtime_id, resources=resources, status=status, index=index, text=text, offset=offset, limit=limit)
    elif isinstance(source, RecoveryExecutionRuntime):
        value = verify_runtime(source)
    else:
        value = build_runtime(source, runtime_id=runtime_id, resources=resources, status=status, index=index, text=text, offset=offset, limit=limit)
    if destination is not None:
        persist_runtime(value, destination, overwrite=overwrite)
    return value


__all__ = ["ARTIFACT_FILES", "ARTIFACT_FIELDS", "ARTIFACT_PREFIX", "BOUNDARY", "DEFAULT_RUNTIME_ID", "FILES", "MANIFEST_ARTIFACT_FIELDS", "MANIFEST_FIELDS", "MANIFEST_PREFIX", "MAX_RUNTIME_BYTES", "RUNTIME_FIELDS", "RUNTIME_PREFIX", "STAGE_FIELDS", "STAGE_PREFIX", "STAGES", "STATES", "RecoveryExecutionRuntime", "RecoveryExecutionRuntimeArtifact", "RecoveryExecutionRuntimeManifest", "RecoveryExecutionRuntimeStage", "address_artifact", "address_manifest", "address_runtime", "address_stage", "build_runtime", "capabilities", "load_runtime", "manifest_document", "manifest_schema", "persist_runtime", "render_runtime_markdown", "run_runtime", "runtime_csv", "runtime_from_mapping", "runtime_json", "runtime_schema", "stage_schema", "verify_runtime", "VERSION"]
