"""Versioned reference manifests and executable adapter conformance.

The reference boundary is deliberately separate from scientific interpretation.
It records what a source is, how it may be accessed, which context it supports,
and whether the adapter contract behaves deterministically for bounded probes.
The manifest contains receipts and metadata only; it never embeds a downloaded
reference payload or a subject-level identifier.
"""

from __future__ import annotations

import csv
import io
import re
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .adapters import AdapterMetadata, EvidenceAdapter, StaticElementAdapter
from .errors import ValidationError
from .models import CandidateElement, EvidenceClaim, ReferenceContext
from .reference_registry import default_reference_registry
from .serialization import content_hash, jsonable, require_non_empty

REFERENCE_MANIFEST_VERSION = "reference-manifest-v1"
REFERENCE_MANIFEST_SCHEMA_VERSION = "reference-manifest-schema-v1"
ADAPTER_CONFORMANCE_VERSION = "adapter-conformance-v1"
REFERENCE_MANIFEST_MAX_ARTIFACTS = 10_000
REFERENCE_MANIFEST_MAX_QUERY_LIMIT = 5_000
ADAPTER_CONFORMANCE_MAX_PROBES = 1_000
_SHA256_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
_PUBLIC_FORBIDDEN_KEYS = {
    "agent",
    "agent_id",
    "model",
    "model_id",
    "language",
    "programming_language",
    "credential",
    "credential_value",
    "secret",
    "secret_key",
    "token",
}


class ReferenceAccessMode(StrEnum):
    """Declared access route for one reference receipt."""

    LOCAL_METADATA = "local_metadata"
    LOCAL_CACHE = "local_cache"
    PUBLIC_HTTPS = "public_https"
    CONTROLLED_DOWNLOAD = "controlled_download"
    INSTITUTIONAL = "institutional"


class ReferenceArtifactState(StrEnum):
    """Availability state of the referenced artifact, not a scientific claim."""

    AVAILABLE = "available"
    PROVISIONAL = "provisional"
    STALE = "stale"
    QUARANTINED = "quarantined"
    UNAVAILABLE = "unavailable"


class AdapterConformanceState(StrEnum):
    """Release state of a bounded adapter contract report."""

    ACCEPTED = "accepted"
    REVIEW = "review"
    BLOCKED = "blocked"


class AdapterConformanceCategory(StrEnum):
    """Independent conformance dimensions retained in the report."""

    METADATA = "metadata"
    MANIFEST = "manifest"
    INVOCATION = "invocation"
    DETERMINISM = "determinism"
    CONTEXT = "context"
    OUTPUT = "output"
    PUBLIC_BOUNDARY = "public_boundary"


def _text(value: Any, field: str) -> str:
    return require_non_empty(str(value), field)


def _texts(values: Iterable[Any], field: str) -> tuple[str, ...]:
    result = tuple(sorted({_text(value, field) for value in values}))
    if not result:
        raise ValidationError(f"{field} requires at least one value")
    return result


def _addressed(body: Mapping[str, Any], prefix: str) -> str:
    return content_hash(body, prefix=prefix)


def _forbidden_keys(value: Any, path: str = "") -> tuple[str, ...]:
    """Find forbidden attribution or credential keys in a public projection."""

    found: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key).lower()
            key_path = f"{path}.{key_text}" if path else key_text
            if key_text in _PUBLIC_FORBIDDEN_KEYS:
                found.append(key_path)
            found.extend(_forbidden_keys(item, key_path))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            found.extend(_forbidden_keys(item, f"{path}[{index}]"))
    return tuple(sorted(set(found)))


@dataclass(frozen=True, slots=True)
class ReferenceArtifact:
    """One source receipt in a versioned reference manifest."""

    artifact_id: str
    adapter_id: str
    source_id: str
    display_name: str
    version: str
    release: str
    uri: str
    license: str
    access_mode: ReferenceAccessMode
    size_bytes: int
    schema_version: str
    coordinate_system: str
    supported_contexts: tuple[str, ...]
    channels: tuple[str, ...]
    state: ReferenceArtifactState = ReferenceArtifactState.AVAILABLE
    checksum: str | None = None
    expected_checksum: str | None = None
    retrieval_policy: str = "bounded"
    notes: str = ""
    content_address: str = ""

    def __post_init__(self) -> None:
        for name in (
            "artifact_id",
            "adapter_id",
            "source_id",
            "display_name",
            "version",
            "release",
            "uri",
            "license",
            "schema_version",
            "coordinate_system",
            "retrieval_policy",
        ):
            _text(getattr(self, name), name)
        if self.size_bytes < 0:
            raise ValidationError("reference artifact size_bytes cannot be negative")
        if not self.uri.startswith(("https://", "file://", "urn:")):
            raise ValidationError("reference artifact URI must be HTTPS, file, or URN")
        if self.access_mode is ReferenceAccessMode.PUBLIC_HTTPS and not self.uri.startswith("https://"):
            raise ValidationError("public_https artifacts require an HTTPS URI")
        for name, checksum in (
            ("checksum", self.checksum),
            ("expected_checksum", self.expected_checksum),
        ):
            if checksum is not None and not _SHA256_PATTERN.fullmatch(checksum):
                raise ValidationError(f"{name} must use sha256:<64 lowercase hex characters>")
        contexts = _texts(self.supported_contexts, "supported_context")
        channels = _texts(self.channels, "channel")
        object.__setattr__(self, "supported_contexts", contexts)
        object.__setattr__(self, "channels", channels)
        expected = _addressed(self.body(), "reference-artifact")
        if self.content_address and self.content_address != expected:
            raise ValidationError("reference artifact content address does not match its body")
        object.__setattr__(self, "content_address", expected)

    def body(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "adapter_id": self.adapter_id,
            "source_id": self.source_id,
            "display_name": self.display_name,
            "version": self.version,
            "release": self.release,
            "uri": self.uri,
            "license": self.license,
            "access_mode": self.access_mode,
            "size_bytes": self.size_bytes,
            "schema_version": self.schema_version,
            "coordinate_system": self.coordinate_system,
            "supported_contexts": self.supported_contexts,
            "channels": self.channels,
            "state": self.state,
            "checksum": self.checksum,
            "expected_checksum": self.expected_checksum,
            "retrieval_policy": self.retrieval_policy,
            "notes": self.notes,
        }

    @property
    def available(self) -> bool:
        return self.state is ReferenceArtifactState.AVAILABLE

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self.body() | {"content_address": self.content_address})


@dataclass(frozen=True, slots=True)
class ReferenceManifest:
    """Immutable, addressed collection of source receipts."""

    manifest_id: str
    release_id: str
    assembly: str
    artifacts: tuple[ReferenceArtifact, ...]
    version: str = REFERENCE_MANIFEST_VERSION
    accepted: bool = False
    content_address: str = ""

    def __post_init__(self) -> None:
        _text(self.manifest_id, "manifest_id")
        _text(self.release_id, "release_id")
        _text(self.assembly, "assembly")
        if not self.artifacts:
            raise ValidationError("reference manifest requires at least one artifact")
        if len(self.artifacts) > REFERENCE_MANIFEST_MAX_ARTIFACTS:
            raise ValidationError("reference manifest exceeds its artifact ceiling")
        expected = _addressed(self.body(), "reference-manifest")
        if self.content_address and self.content_address != expected:
            raise ValidationError("reference manifest content address does not match its body")
        object.__setattr__(self, "content_address", expected)

    @property
    def artifact_count(self) -> int:
        return len(self.artifacts)

    @property
    def available_count(self) -> int:
        return sum(item.available for item in self.artifacts)

    @property
    def adapter_ids(self) -> tuple[str, ...]:
        return tuple(sorted({item.adapter_id for item in self.artifacts}))

    def body(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "manifest_id": self.manifest_id,
            "release_id": self.release_id,
            "assembly": self.assembly,
            "artifacts": self.artifacts,
            "accepted": self.accepted,
        }

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self.body() | {"content_address": self.content_address}) | {
            "artifact_count": self.artifact_count,
            "available_count": self.available_count,
        }


def _artifact_issues(artifacts: Sequence[ReferenceArtifact]) -> tuple[str, ...]:
    issues: list[str] = []
    ids = [item.artifact_id for item in artifacts]
    if len(ids) != len(set(ids)):
        issues.append("artifact-ids-unique")
    if tuple(ids) != tuple(sorted(ids)):
        issues.append("artifact-order")
    for artifact in artifacts:
        if artifact.content_address != _addressed(artifact.body(), "reference-artifact"):
            issues.append(f"artifact-address:{artifact.artifact_id}")
        public_projection = artifact.to_dict()
        forbidden = _forbidden_keys(public_projection)
        if forbidden:
            issues.append(f"artifact-public-boundary:{artifact.artifact_id}")
    return tuple(issues)


def verify_reference_manifest(manifest: ReferenceManifest) -> tuple[str, ...]:
    """Return independent manifest failures without mutating the receipt."""

    issues = list(_artifact_issues(manifest.artifacts))
    if manifest.version != REFERENCE_MANIFEST_VERSION:
        issues.append("version")
    if not manifest.release_id.strip():
        issues.append("release-id")
    if manifest.accepted != (not issues):
        issues.append("accepted-state")
    if manifest.content_address != _addressed(manifest.body(), "reference-manifest"):
        issues.append("content-address")
    return tuple(issues)


def build_reference_manifest(
    artifacts: Iterable[ReferenceArtifact],
    *,
    manifest_id: str = "glio-noncode-reference-manifest",
    release_id: str = "reference-release-v1",
    assembly: str = "multi-assembly",
) -> ReferenceManifest:
    """Build a stable manifest, sorting receipts before addressing the body."""

    normalized = tuple(sorted(tuple(artifacts), key=lambda item: item.artifact_id))
    if not normalized:
        raise ValidationError("reference manifest requires at least one artifact")
    issues = _artifact_issues(normalized)
    body = {
        "version": REFERENCE_MANIFEST_VERSION,
        "manifest_id": manifest_id,
        "release_id": release_id,
        "assembly": assembly,
        "artifacts": normalized,
        "accepted": not issues,
    }
    return ReferenceManifest(
        manifest_id=manifest_id,
        release_id=release_id,
        assembly=assembly,
        artifacts=normalized,
        accepted=not issues,
        content_address=_addressed(body, "reference-manifest"),
    )


def reference_manifest_from_dict(value: Mapping[str, Any]) -> ReferenceManifest:
    """Reopen and verify a serialized manifest."""

    raw_artifacts = value.get("artifacts", ())
    if not isinstance(raw_artifacts, list):
        raise ValidationError("reference manifest artifacts must be an array")
    artifacts: list[ReferenceArtifact] = []
    for raw in raw_artifacts:
        if not isinstance(raw, Mapping):
            raise ValidationError("reference manifest artifact must be an object")
        if not str(raw.get("content_address", "")).strip():
            raise ValidationError("reference manifest artifact content address is required")
        artifacts.append(
            ReferenceArtifact(
                artifact_id=str(raw.get("artifact_id", "")),
                adapter_id=str(raw.get("adapter_id", "")),
                source_id=str(raw.get("source_id", "")),
                display_name=str(raw.get("display_name", "")),
                version=str(raw.get("version", "")),
                release=str(raw.get("release", "")),
                uri=str(raw.get("uri", "")),
                license=str(raw.get("license", "")),
                access_mode=ReferenceAccessMode(str(raw.get("access_mode", ""))),
                size_bytes=int(raw.get("size_bytes", 0)),
                schema_version=str(raw.get("schema_version", "")),
                coordinate_system=str(raw.get("coordinate_system", "")),
                supported_contexts=tuple(str(item) for item in raw.get("supported_contexts", ())),
                channels=tuple(str(item) for item in raw.get("channels", ())),
                state=ReferenceArtifactState(str(raw.get("state", ReferenceArtifactState.AVAILABLE.value))),
                checksum=None if raw.get("checksum") is None else str(raw.get("checksum")),
                expected_checksum=None if raw.get("expected_checksum") is None else str(raw.get("expected_checksum")),
                retrieval_policy=str(raw.get("retrieval_policy", "bounded")),
                notes=str(raw.get("notes", "")),
                content_address=str(raw.get("content_address", "")),
            )
        )
    try:
        if not str(value.get("content_address", "")).strip():
            raise ValidationError("reference manifest content address is required")
        manifest = ReferenceManifest(
            manifest_id=str(value.get("manifest_id", "")),
            release_id=str(value.get("release_id", "")),
            assembly=str(value.get("assembly", "")),
            artifacts=tuple(artifacts),
            version=str(value.get("version", "")),
            accepted=bool(value.get("accepted", False)),
            content_address=str(value.get("content_address", "")),
        )
    except (TypeError, ValueError) as exc:
        raise ValidationError("reference manifest cannot be decoded") from exc
    issues = verify_reference_manifest(manifest)
    if value.get("artifact_count", manifest.artifact_count) != manifest.artifact_count:
        issues = (*issues, "artifact-count")
    if value.get("available_count", manifest.available_count) != manifest.available_count:
        issues = (*issues, "available-count")
    if issues:
        raise ValidationError("invalid reference manifest: " + ", ".join(issues))
    return manifest


def reference_manifest_summary(manifest: ReferenceManifest) -> dict[str, Any]:
    """Return compact counts suitable for health and dashboard clients."""

    states = Counter(item.state.value for item in manifest.artifacts)
    access_modes = Counter(item.access_mode.value for item in manifest.artifacts)
    adapters = Counter(item.adapter_id for item in manifest.artifacts)
    body = {
        "manifest_id": manifest.manifest_id,
        "release_id": manifest.release_id,
        "assembly": manifest.assembly,
        "manifest_address": manifest.content_address,
        "accepted": manifest.accepted,
        "artifact_count": manifest.artifact_count,
        "available_count": manifest.available_count,
        "adapter_count": len(manifest.adapter_ids),
        "states": dict(sorted(states.items())),
        "access_modes": dict(sorted(access_modes.items())),
        "adapters": dict(sorted(adapters.items())),
        "public_boundary": {"safe": not _forbidden_keys(manifest.to_dict()), "projection": "public"},
    }
    return body | {"content_address": _addressed(body, "reference-manifest-summary")}


def query_reference_manifest(
    manifest: ReferenceManifest,
    *,
    artifact_id: str | None = None,
    adapter_id: str | None = None,
    source_id: str | None = None,
    context: str | None = None,
    channel: str | None = None,
    state: ReferenceArtifactState | str | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[ReferenceArtifact, ...]:
    """Filter receipts without changing their stable order or addresses."""

    if offset < 0:
        raise ValidationError("reference manifest query offset cannot be negative")
    if limit < 1 or limit > REFERENCE_MANIFEST_MAX_QUERY_LIMIT:
        raise ValidationError("reference manifest query limit is outside the supported range")
    selected_state = ReferenceArtifactState(state) if isinstance(state, str) else state
    needle = text.strip().lower() if text else None
    rows = []
    for artifact in manifest.artifacts:
        haystack = " ".join(
            (artifact.artifact_id, artifact.adapter_id, artifact.source_id, artifact.display_name, artifact.release)
        ).lower()
        if artifact_id and artifact.artifact_id != artifact_id:
            continue
        if adapter_id and artifact.adapter_id != adapter_id:
            continue
        if source_id and artifact.source_id != source_id:
            continue
        if context and context not in artifact.supported_contexts:
            continue
        if channel and channel not in artifact.channels:
            continue
        if selected_state and artifact.state is not selected_state:
            continue
        if needle and needle not in haystack:
            continue
        rows.append(artifact)
    return tuple(rows[offset : offset + limit])


def reference_manifest_csv(manifest: ReferenceManifest) -> str:
    """Export receipt metadata with stable columns."""

    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        (
            "artifact_id",
            "adapter_id",
            "source_id",
            "version",
            "release",
            "uri",
            "license",
            "access_mode",
            "state",
            "size_bytes",
            "checksum",
            "coordinate_system",
            "supported_contexts",
            "channels",
            "content_address",
        )
    )
    for artifact in manifest.artifacts:
        writer.writerow(
            (
                artifact.artifact_id,
                artifact.adapter_id,
                artifact.source_id,
                artifact.version,
                artifact.release,
                artifact.uri,
                artifact.license,
                artifact.access_mode.value,
                artifact.state.value,
                artifact.size_bytes,
                artifact.checksum or "",
                artifact.coordinate_system,
                ";".join(artifact.supported_contexts),
                ";".join(artifact.channels),
                artifact.content_address,
            )
        )
    return output.getvalue()


def reference_manifest_markdown(manifest: ReferenceManifest) -> str:
    """Render a reviewer-facing receipt summary."""

    lines = [
        "# Reference Manifest",
        "",
        f"- Manifest: `{manifest.manifest_id}`",
        f"- Release: `{manifest.release_id}`",
        f"- Assembly: `{manifest.assembly}`",
        f"- Accepted: `{str(manifest.accepted).lower()}`",
        f"- Artifacts: `{manifest.artifact_count}`",
        f"- Content address: `{manifest.content_address}`",
        "",
        "| Artifact | Adapter | Source | Version | State | Access | Contexts |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for artifact in manifest.artifacts:
        lines.append(
            "| "
            + " | ".join(
                (
                    artifact.artifact_id,
                    artifact.adapter_id,
                    artifact.source_id,
                    artifact.version,
                    artifact.state.value,
                    artifact.access_mode.value,
                    ";".join(artifact.supported_contexts),
                )
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def reference_manifest_schema() -> dict[str, Any]:
    """Return the closed public schema for manifest exchange."""

    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "GLIO-NONCODE Reference Manifest",
        "type": "object",
        "required": ["version", "manifest_id", "release_id", "assembly", "artifacts", "accepted", "content_address"],
        "properties": {
            "version": {"const": REFERENCE_MANIFEST_VERSION},
            "manifest_id": {"type": "string", "minLength": 1},
            "release_id": {"type": "string", "minLength": 1},
            "assembly": {"type": "string", "minLength": 1},
            "accepted": {"type": "boolean"},
            "artifact_count": {"type": "integer", "minimum": 1},
            "available_count": {"type": "integer", "minimum": 0},
            "content_address": {"type": "string", "pattern": "^reference-manifest:[0-9a-f]{64}$"},
            "artifacts": {
                "type": "array",
                "minItems": 1,
                "maxItems": REFERENCE_MANIFEST_MAX_ARTIFACTS,
                "items": {
                    "type": "object",
                    "required": [
                        "artifact_id",
                        "adapter_id",
                        "source_id",
                        "display_name",
                        "version",
                        "release",
                        "uri",
                        "license",
                        "access_mode",
                        "state",
                        "supported_contexts",
                        "channels",
                        "content_address",
                    ],
                    "properties": {
                        "artifact_id": {"type": "string", "minLength": 1},
                        "adapter_id": {"type": "string", "minLength": 1},
                        "source_id": {"type": "string", "minLength": 1},
                        "display_name": {"type": "string", "minLength": 1},
                        "version": {"type": "string", "minLength": 1},
                        "release": {"type": "string", "minLength": 1},
                        "uri": {"type": "string", "pattern": "^(https://|file://|urn:)"},
                        "license": {"type": "string", "minLength": 1},
                        "access_mode": {"enum": [item.value for item in ReferenceAccessMode]},
                        "state": {"enum": [item.value for item in ReferenceArtifactState]},
                        "size_bytes": {"type": "integer", "minimum": 0},
                        "supported_contexts": {"type": "array", "minItems": 1, "items": {"type": "string"}},
                        "channels": {"type": "array", "minItems": 1, "items": {"type": "string"}},
                        "content_address": {"type": "string", "pattern": "^reference-artifact:[0-9a-f]{64}$"},
                    },
                    "additionalProperties": True,
                },
            },
        },
        "additionalProperties": True,
    }


@dataclass(frozen=True, slots=True)
class AdapterConformanceProbe:
    """One bounded request used to test an adapter's deterministic behavior."""

    probe_id: str
    variant_id: str
    context: ReferenceContext
    element_id: str | None = None
    expected_element_ids: tuple[str, ...] = ()
    expected_claim_count: int | None = None

    def __post_init__(self) -> None:
        _text(self.probe_id, "probe_id")
        _text(self.variant_id, "variant_id")
        if self.element_id is not None:
            _text(self.element_id, "element_id")
        if self.expected_claim_count is not None and self.expected_claim_count < 0:
            raise ValidationError("expected_claim_count cannot be negative")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class AdapterConformanceCheck:
    """One independently addressed adapter conformance result."""

    check_id: str
    category: AdapterConformanceCategory
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str = ""

    def __post_init__(self) -> None:
        _text(self.check_id, "check_id")
        _text(self.detail, "detail")
        body = self.body()
        expected = _addressed(body, "adapter-conformance-check")
        if self.content_address and self.content_address != expected:
            raise ValidationError("adapter conformance check address does not match its body")
        object.__setattr__(self, "content_address", expected)

    def body(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "category": self.category,
            "passed": self.passed,
            "observed": self.observed,
            "required": self.required,
            "detail": self.detail,
        }

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self.body() | {"content_address": self.content_address})


@dataclass(frozen=True, slots=True)
class AdapterConformanceReport:
    """Complete bounded conformance report for one adapter and manifest."""

    adapter_id: str
    manifest_id: str
    artifact_id: str | None
    metadata_address: str
    probes: tuple[AdapterConformanceProbe, ...]
    checks: tuple[AdapterConformanceCheck, ...]
    invocation_count: int
    element_count: int
    claim_count: int
    state: AdapterConformanceState
    accepted: bool
    version: str = ADAPTER_CONFORMANCE_VERSION
    content_address: str = ""

    def __post_init__(self) -> None:
        _text(self.adapter_id, "adapter_id")
        _text(self.manifest_id, "manifest_id")
        if self.artifact_id is not None:
            _text(self.artifact_id, "artifact_id")
        if self.invocation_count < 0 or self.element_count < 0 or self.claim_count < 0:
            raise ValidationError("adapter conformance counts cannot be negative")
        expected = _addressed(self.body(), "adapter-conformance")
        if self.content_address and self.content_address != expected:
            raise ValidationError("adapter conformance address does not match its body")
        object.__setattr__(self, "content_address", expected)

    def body(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "adapter_id": self.adapter_id,
            "manifest_id": self.manifest_id,
            "artifact_id": self.artifact_id,
            "metadata_address": self.metadata_address,
            "probes": self.probes,
            "checks": self.checks,
            "invocation_count": self.invocation_count,
            "element_count": self.element_count,
            "claim_count": self.claim_count,
            "state": self.state,
            "accepted": self.accepted,
        }

    @property
    def passed_checks(self) -> int:
        return sum(item.passed for item in self.checks)

    @property
    def failed_checks(self) -> int:
        return len(self.checks) - self.passed_checks

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self.body() | {"content_address": self.content_address}) | {
            "check_count": len(self.checks),
            "passed_checks": self.passed_checks,
            "failed_checks": self.failed_checks,
        }


def _check(
    check_id: str,
    category: AdapterConformanceCategory,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> AdapterConformanceCheck:
    return AdapterConformanceCheck(check_id, category, bool(passed), observed, required, detail)


def _safe_output(value: Any) -> tuple[Any, tuple[str, ...]]:
    public = jsonable(value)
    return public, _forbidden_keys(public)


def _probe_result(
    adapter: EvidenceAdapter,
    probe: AdapterConformanceProbe,
    artifact: ReferenceArtifact | None,
) -> tuple[list[AdapterConformanceCheck], int, int, int]:
    checks: list[AdapterConformanceCheck] = []
    invocation_count = 0
    element_count = 0
    claim_count = 0
    try:
        first = adapter.resolve_elements(probe.variant_id, probe.context)
        second = adapter.resolve_elements(probe.variant_id, probe.context)
        invocation_count += 2
        first_public, first_forbidden = _safe_output(first)
        second_public, second_forbidden = _safe_output(second)
        checks.append(
            _check(
                f"{probe.probe_id}:resolve-deterministic",
                AdapterConformanceCategory.DETERMINISM,
                first_public == second_public,
                first_public == second_public,
                True,
                "repeated element resolution has the same canonical projection",
            )
        )
        checks.append(
            _check(
                f"{probe.probe_id}:resolve-public-boundary",
                AdapterConformanceCategory.PUBLIC_BOUNDARY,
                not first_forbidden and not second_forbidden,
                first_forbidden + second_forbidden,
                (),
                "element projections contain no forbidden attribution or credential keys",
            )
        )
        if not isinstance(first, tuple) or not isinstance(second, tuple):
            checks.append(
                _check(
                    f"{probe.probe_id}:resolve-return-type",
                    AdapterConformanceCategory.OUTPUT,
                    False,
                    type(first).__name__,
                    "tuple",
                    "adapter resolution must return a tuple",
                )
            )
            return checks, invocation_count, 0, 0
        valid_elements = [item for item in first if isinstance(item, CandidateElement)]
        element_count += len(valid_elements)
        checks.append(
            _check(
                f"{probe.probe_id}:resolve-item-types",
                AdapterConformanceCategory.OUTPUT,
                len(valid_elements) == len(first),
                len(valid_elements),
                len(first),
                "every resolution item is a CandidateElement",
            )
        )
        element_ids = tuple(item.element_id for item in valid_elements)
        checks.append(
            _check(
                f"{probe.probe_id}:resolve-identities-unique",
                AdapterConformanceCategory.OUTPUT,
                len(element_ids) == len(set(element_ids)),
                len(element_ids),
                len(set(element_ids)),
                "element identities are unique within one adapter response",
            )
        )
        checks.append(
            _check(
                f"{probe.probe_id}:resolve-context",
                AdapterConformanceCategory.CONTEXT,
                all(item.context.key == probe.context.key for item in valid_elements),
                sorted({item.context.key for item in valid_elements}),
                [probe.context.key],
                "resolved elements remain in the requested context",
            )
        )
        if probe.expected_element_ids:
            checks.append(
                _check(
                    f"{probe.probe_id}:resolve-expected-elements",
                    AdapterConformanceCategory.OUTPUT,
                    element_ids == tuple(sorted(probe.expected_element_ids)),
                    element_ids,
                    tuple(sorted(probe.expected_element_ids)),
                    "bounded fixture expectations are preserved exactly",
                )
            )
        for element in valid_elements:
            try:
                claims_first = adapter.collect_claims(probe.variant_id, element.element_id, probe.context)
                claims_second = adapter.collect_claims(probe.variant_id, element.element_id, probe.context)
                invocation_count += 2
                claims_first_public, claims_first_forbidden = _safe_output(claims_first)
                claims_second_public, claims_second_forbidden = _safe_output(claims_second)
                checks.append(
                    _check(
                        f"{probe.probe_id}:{element.element_id}:claims-deterministic",
                        AdapterConformanceCategory.DETERMINISM,
                        claims_first_public == claims_second_public,
                        claims_first_public == claims_second_public,
                        True,
                        "repeated claim collection has the same canonical projection",
                    )
                )
                checks.append(
                    _check(
                        f"{probe.probe_id}:{element.element_id}:claims-public-boundary",
                        AdapterConformanceCategory.PUBLIC_BOUNDARY,
                        not claims_first_forbidden and not claims_second_forbidden,
                        claims_first_forbidden + claims_second_forbidden,
                        (),
                        "claim projections contain no forbidden attribution or credential keys",
                    )
                )
                if not isinstance(claims_first, tuple):
                    checks.append(
                        _check(
                            f"{probe.probe_id}:{element.element_id}:claims-return-type",
                            AdapterConformanceCategory.OUTPUT,
                            False,
                            type(claims_first).__name__,
                            "tuple",
                            "adapter claim collection must return a tuple",
                        )
                    )
                    continue
                valid_claims = [item for item in claims_first if isinstance(item, EvidenceClaim)]
                claim_count += len(valid_claims)
                checks.append(
                    _check(
                        f"{probe.probe_id}:{element.element_id}:claim-item-types",
                        AdapterConformanceCategory.OUTPUT,
                        len(valid_claims) == len(claims_first),
                        len(valid_claims),
                        len(claims_first),
                        "every claim is an EvidenceClaim",
                    )
                )
                checks.append(
                    _check(
                        f"{probe.probe_id}:{element.element_id}:claim-context",
                        AdapterConformanceCategory.CONTEXT,
                        all(item.context.key == probe.context.key for item in valid_claims),
                        sorted({item.context.key for item in valid_claims}),
                        [probe.context.key],
                        "claims remain in the requested context",
                    )
                )
                if artifact is not None:
                    checks.append(
                        _check(
                            f"{probe.probe_id}:{element.element_id}:claim-source",
                            AdapterConformanceCategory.OUTPUT,
                            all(item.source_id == artifact.source_id for item in valid_claims),
                            sorted({item.source_id for item in valid_claims}),
                            [artifact.source_id],
                            "claim source IDs remain attached to the declared artifact",
                        )
                    )
                if probe.expected_claim_count is not None:
                    checks.append(
                        _check(
                            f"{probe.probe_id}:{element.element_id}:claim-count",
                            AdapterConformanceCategory.OUTPUT,
                            len(valid_claims) == probe.expected_claim_count,
                            len(valid_claims),
                            probe.expected_claim_count,
                            "bounded fixture claim count is preserved",
                        )
                    )
            except Exception as exc:  # pragma: no cover - exercised by failure probes
                checks.append(
                    _check(
                        f"{probe.probe_id}:{element.element_id}:claims-exception",
                        AdapterConformanceCategory.INVOCATION,
                        False,
                        type(exc).__name__,
                        "no exception",
                        "claim collection failed for a bounded probe",
                    )
                )
    except Exception as exc:  # pragma: no cover - exercised by failure probes
        checks.append(
            _check(
                f"{probe.probe_id}:resolve-exception",
                AdapterConformanceCategory.INVOCATION,
                False,
                type(exc).__name__,
                "no exception",
                "element resolution failed for a bounded probe",
            )
        )
    return checks, invocation_count, element_count, claim_count


def conform_adapter(
    adapter: EvidenceAdapter,
    manifest: ReferenceManifest,
    probes: Sequence[AdapterConformanceProbe],
) -> AdapterConformanceReport:
    """Run bounded, repeatable conformance checks against one registered adapter."""

    if len(probes) > ADAPTER_CONFORMANCE_MAX_PROBES:
        raise ValidationError("adapter conformance probe count exceeds its ceiling")
    metadata = adapter.metadata
    metadata_address = content_hash(metadata.to_dict(), prefix="adapter-metadata")
    artifact = next((item for item in manifest.artifacts if item.adapter_id == metadata.adapter_id), None)
    checks: list[AdapterConformanceCheck] = []
    checks.append(
        _check(
            "metadata:adapter-id",
            AdapterConformanceCategory.METADATA,
            bool(metadata.adapter_id.strip()),
            metadata.adapter_id,
            "non-empty adapter ID",
            "adapter metadata declares an addressable ID",
        )
    )
    checks.append(
        _check(
            "metadata:channels",
            AdapterConformanceCategory.METADATA,
            bool(metadata.channels),
            len(metadata.channels),
            ">=1",
            "adapter metadata declares at least one channel",
        )
    )
    checks.append(
        _check(
            "manifest:adapter-receipt",
            AdapterConformanceCategory.MANIFEST,
            artifact is not None,
            None if artifact is None else artifact.artifact_id,
            metadata.adapter_id,
            "the versioned manifest names a receipt for the adapter",
        )
    )
    if artifact is not None:
        checks.extend(
            (
                _check(
                    "manifest:artifact-available",
                    AdapterConformanceCategory.MANIFEST,
                    artifact.available,
                    artifact.state.value,
                    ReferenceArtifactState.AVAILABLE.value,
                    "conformance only accepts an available source receipt",
                ),
                _check(
                    "manifest:version-match",
                    AdapterConformanceCategory.MANIFEST,
                    artifact.version == metadata.version,
                    artifact.version,
                    metadata.version,
                    "manifest and adapter versions agree",
                ),
                _check(
                    "manifest:license-match",
                    AdapterConformanceCategory.MANIFEST,
                    artifact.license == metadata.license,
                    artifact.license,
                    metadata.license,
                    "manifest and adapter license declarations agree",
                ),
                _check(
                    "manifest:channel-coverage",
                    AdapterConformanceCategory.MANIFEST,
                    set(metadata.channels).issubset(set(artifact.channels)),
                    sorted(metadata.channels),
                    sorted(artifact.channels),
                    "manifest receipt covers every adapter channel",
                ),
            )
        )
    checks.append(
        _check(
            "manifest:accepted",
            AdapterConformanceCategory.MANIFEST,
            manifest.accepted,
            manifest.accepted,
            True,
            "adapter conformance consumes an accepted manifest",
        )
    )
    invocation_count = 0
    element_count = 0
    claim_count = 0
    for probe in probes:
        probe_checks, calls, elements, claims = _probe_result(adapter, probe, artifact)
        checks.extend(probe_checks)
        invocation_count += calls
        element_count += elements
        claim_count += claims
    failed_categories = {item.category for item in checks if not item.passed}
    if not manifest.accepted or AdapterConformanceCategory.MANIFEST in failed_categories:
        state = AdapterConformanceState.BLOCKED
    elif failed_categories:
        state = AdapterConformanceState.REVIEW
    else:
        state = AdapterConformanceState.ACCEPTED
    body = {
        "version": ADAPTER_CONFORMANCE_VERSION,
        "adapter_id": metadata.adapter_id,
        "manifest_id": manifest.manifest_id,
        "artifact_id": None if artifact is None else artifact.artifact_id,
        "metadata_address": metadata_address,
        "probes": tuple(probes),
        "checks": tuple(checks),
        "invocation_count": invocation_count,
        "element_count": element_count,
        "claim_count": claim_count,
        "state": state,
        "accepted": state is AdapterConformanceState.ACCEPTED,
    }
    return AdapterConformanceReport(
        adapter_id=metadata.adapter_id,
        manifest_id=manifest.manifest_id,
        artifact_id=None if artifact is None else artifact.artifact_id,
        metadata_address=metadata_address,
        probes=tuple(probes),
        checks=tuple(checks),
        invocation_count=invocation_count,
        element_count=element_count,
        claim_count=claim_count,
        state=state,
        accepted=state is AdapterConformanceState.ACCEPTED,
        content_address=_addressed(body, "adapter-conformance"),
    )


def adapter_conformance_schema() -> dict[str, Any]:
    """Return the closed public schema for conformance reports."""

    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "GLIO-NONCODE Adapter Conformance Report",
        "type": "object",
        "required": ["version", "adapter_id", "manifest_id", "checks", "state", "accepted", "content_address"],
        "properties": {
            "version": {"const": ADAPTER_CONFORMANCE_VERSION},
            "adapter_id": {"type": "string", "minLength": 1},
            "manifest_id": {"type": "string", "minLength": 1},
            "checks": {"type": "array"},
            "state": {"enum": [item.value for item in AdapterConformanceState]},
            "accepted": {"type": "boolean"},
            "content_address": {"type": "string", "pattern": "^adapter-conformance:[0-9a-f]{64}$"},
        },
        "additionalProperties": True,
    }


def adapter_conformance_markdown(report: AdapterConformanceReport) -> str:
    """Render an adapter report for review without payload data."""

    lines = [
        "# Adapter Conformance",
        "",
        f"- Adapter: `{report.adapter_id}`",
        f"- Manifest: `{report.manifest_id}`",
        f"- State: `{report.state.value}`",
        f"- Checks: `{report.passed_checks}/{len(report.checks)}`",
        f"- Invocations: `{report.invocation_count}`",
        f"- Elements: `{report.element_count}`",
        f"- Claims: `{report.claim_count}`",
        f"- Content address: `{report.content_address}`",
        "",
        "| Check | Category | Passed | Detail |",
        "| --- | --- | --- | --- |",
    ]
    for check in report.checks:
        detail = check.detail.replace("|", "\\|")
        lines.append(
            f"| {check.check_id} | {check.category.value} | {str(check.passed).lower()} | {detail} |"
        )
    return "\n".join(lines) + "\n"


def adapter_conformance_csv(report: AdapterConformanceReport) -> str:
    """Export one stable review row per conformance check."""

    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(("adapter_id", "manifest_id", "check_id", "category", "passed", "detail", "content_address"))
    for check in report.checks:
        writer.writerow((report.adapter_id, report.manifest_id, check.check_id, check.category.value, check.passed, check.detail, check.content_address))
    return output.getvalue()


def build_default_reference_manifest() -> ReferenceManifest:
    """Build a public metadata manifest from the checked-in assembly registry."""

    artifacts = tuple(
        ReferenceArtifact(
            artifact_id=f"assembly:{assembly.assembly_id}",
            adapter_id="reference-assembly-registry",
            source_id=assembly.source_ids[0] if assembly.source_ids else "reference-registry",
            display_name=f"{assembly.canonical_name} assembly metadata",
            version=assembly.release,
            release=assembly.release,
            uri=f"urn:glio-noncode:reference-assembly:{assembly.assembly_id}",
            license="public assembly metadata",
            access_mode=ReferenceAccessMode.LOCAL_METADATA,
            size_bytes=0,
            schema_version="reference-assembly-v1",
            coordinate_system=assembly.coordinate_system.value,
            supported_contexts=(assembly.assembly_id,),
            channels=("assembly_identity", "coordinate_projection"),
            notes="metadata receipt only; no reference payload is embedded",
        )
        for assembly in default_reference_registry().all()
    )
    return build_reference_manifest(
        artifacts,
        manifest_id="glio-noncode-reference-manifest",
        release_id="references-2026.08",
        assembly="human-reference-assemblies",
    )


def adapter_conformance_input_from_dict(
    value: Mapping[str, Any],
) -> tuple[StaticElementAdapter, ReferenceManifest, tuple[AdapterConformanceProbe, ...]]:
    """Decode a portable static-adapter conformance input document."""

    manifest_raw = value.get("manifest")
    if not isinstance(manifest_raw, Mapping):
        raise ValidationError("adapter conformance input requires a manifest object")
    manifest = reference_manifest_from_dict(manifest_raw)
    metadata_raw = value.get("metadata")
    if not isinstance(metadata_raw, Mapping):
        raise ValidationError("adapter conformance input requires adapter metadata")
    metadata = AdapterMetadata(
        adapter_id=str(metadata_raw.get("adapter_id", "")),
        display_name=str(metadata_raw.get("display_name", "")),
        version=str(metadata_raw.get("version", "")),
        license=str(metadata_raw.get("license", "")),
        data_access=str(metadata_raw.get("data_access", "")),
        supported_contexts=tuple(str(item) for item in metadata_raw.get("supported_contexts", ())),
        channels=tuple(str(item) for item in metadata_raw.get("channels", ())),
        failure_modes=tuple(str(item) for item in metadata_raw.get("failure_modes", ())),
        validation_status=str(metadata_raw.get("validation_status", "unvalidated")),
        documentation_url=None if metadata_raw.get("documentation_url") is None else str(metadata_raw.get("documentation_url")),
    )
    probe_raw = value.get("probes", ())
    if not isinstance(probe_raw, list):
        raise ValidationError("adapter conformance probes must be an array")
    probes: list[AdapterConformanceProbe] = []
    contexts: dict[str, ReferenceContext] = {}
    for raw in probe_raw:
        if not isinstance(raw, Mapping):
            raise ValidationError("adapter conformance probe must be an object")
        context_raw = raw.get("context", {})
        if not isinstance(context_raw, Mapping):
            raise ValidationError("adapter conformance probe context must be an object")
        context = ReferenceContext.from_dict(context_raw)
        contexts[context.key] = context
        probes.append(
            AdapterConformanceProbe(
                probe_id=str(raw.get("probe_id", "")),
                variant_id=str(raw.get("variant_id", "")),
                context=context,
                element_id=None if raw.get("element_id") is None else str(raw.get("element_id")),
                expected_element_ids=tuple(str(item) for item in raw.get("expected_element_ids", ())),
                expected_claim_count=None if raw.get("expected_claim_count") is None else int(raw.get("expected_claim_count")),
            )
        )
    default_context = next(iter(contexts.values()), ReferenceContext("GRCh38", "unknown", "unknown", "unknown"))
    elements_raw = value.get("elements", ())
    if not isinstance(elements_raw, list):
        raise ValidationError("adapter conformance elements must be an array")
    elements = tuple(
        CandidateElement.from_dict(item, default_context)
        for item in elements_raw
        if isinstance(item, Mapping)
    )
    return StaticElementAdapter(metadata, elements), manifest, tuple(probes)


__all__ = [
    "ADAPTER_CONFORMANCE_MAX_PROBES",
    "ADAPTER_CONFORMANCE_VERSION",
    "AdapterConformanceCategory",
    "AdapterConformanceCheck",
    "AdapterConformanceProbe",
    "AdapterConformanceReport",
    "AdapterConformanceState",
    "REFERENCE_MANIFEST_MAX_ARTIFACTS",
    "REFERENCE_MANIFEST_MAX_QUERY_LIMIT",
    "REFERENCE_MANIFEST_SCHEMA_VERSION",
    "REFERENCE_MANIFEST_VERSION",
    "ReferenceAccessMode",
    "ReferenceArtifact",
    "ReferenceArtifactState",
    "ReferenceManifest",
    "adapter_conformance_csv",
    "adapter_conformance_input_from_dict",
    "adapter_conformance_markdown",
    "adapter_conformance_schema",
    "build_default_reference_manifest",
    "build_reference_manifest",
    "conform_adapter",
    "query_reference_manifest",
    "reference_manifest_csv",
    "reference_manifest_from_dict",
    "reference_manifest_markdown",
    "reference_manifest_schema",
    "reference_manifest_summary",
    "verify_reference_manifest",
]
