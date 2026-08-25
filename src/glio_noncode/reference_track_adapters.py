"""Declared public reference-track adapters and conformance receipts.

Reference rows are useful only when their source boundary is carried with the
reading. This module composes the columnar interval index with a versioned
adapter declaration: source identity, license, access mode, coordinate
convention, supported context patterns, channels, retrieval limits, and
limitations are required before a track can be queried by atlas code.

The adapter is intentionally local and dependency-free. It can wrap a
downloaded public snapshot, a controlled local cache, or a small synthetic
fixture, but the output always states which of those modes was declared. It
does not turn an interval overlap into an activity, disease, or causal claim.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .reference_interval_index import (
    ContextQueryMode,
    LatticeContext,
    PublicReferenceRecord,
    ReferenceIndexBuildIssue,
    ReferenceIndexQuery,
    ReferenceIndexQueryReport,
    ReferenceIndexQueryState,
    ReferenceIntervalIndex,
    build_reference_interval_index,
    match_context,
)
from .reference_manifest import (
    ReferenceAccessMode,
    ReferenceArtifact,
    ReferenceArtifactState,
)
from .reference_registry import CoordinateSystem
from .serialization import content_hash, jsonable, require_non_empty


REFERENCE_TRACK_ADAPTER_VERSION = "reference-track-adapter-v1"
REFERENCE_TRACK_ADAPTER_SCHEMA_VERSION = "reference-track-adapter-schema-v1"
REFERENCE_TRACK_ADAPTER_ROW_SCHEMA_VERSION = "reference-track-row-v1"
REFERENCE_TRACK_ADAPTER_MAX_PROBES = 64
REFERENCE_TRACK_ADAPTER_MAX_ADAPTERS = 256
REFERENCE_TRACK_ADAPTER_MAX_QUERY_LIMIT = 5_000
REFERENCE_TRACK_ADAPTER_MAX_RECORDS = 1_000_000

_PUBLIC_FORBIDDEN_KEYS = frozenset(
    {
        "agent",
        "agent_id",
        "agent_name",
        "assistant",
        "assistant_id",
        "assistant_name",
        "author",
        "author_id",
        "author_name",
        "contact_name",
        "credential",
        "credential_value",
        "email",
        "generated_by",
        "individual_id",
        "language",
        "medical_record_number",
        "model",
        "model_id",
        "model_name",
        "model_version",
        "participant_id",
        "patient_id",
        "phone",
        "primary_agent",
        "programming_language",
        "produced_by",
        "sample_id",
        "secret",
        "secret_key",
        "subject_id",
        "token",
    }
)


class ReferenceTrackAdapterState(StrEnum):
    """Operational state of a declared adapter."""

    ACCEPTED = "accepted"
    REVIEW = "review"
    BLOCKED = "blocked"
    ABSTAINED = "abstained"


class ReferenceTrackQueryState(StrEnum):
    """Public result states for an adapter-backed feature reading."""

    SUPPORTED = "supported"
    ABSENT = "absent"
    OUT_OF_DOMAIN = "out_of_domain"
    TRUNCATED = "truncated"
    ABSTAINED = "abstained"
    INVALID = "invalid"


class ReferenceTrackConformanceCategory(StrEnum):
    """Independent adapter contract dimensions in a conformance report."""

    METADATA = "metadata"
    ARTIFACT = "artifact"
    INDEX = "index"
    INVOCATION = "invocation"
    DETERMINISM = "determinism"
    CONTEXT = "context"
    OUTPUT = "output"
    PUBLIC_BOUNDARY = "public_boundary"


def _text(value: Any, field: str) -> str:
    return require_non_empty(str(value), field)


def _unique_texts(values: Iterable[Any], field: str) -> tuple[str, ...]:
    result = tuple(sorted({_text(value, field) for value in values}))
    if not result:
        raise ValidationError(f"{field} requires at least one value")
    return result


def _optional_texts(values: Iterable[Any]) -> tuple[str, ...]:
    return tuple(sorted({str(value).strip() for value in values if str(value).strip()}))


def _public_projection(value: Any) -> Any:
    value = jsonable(value)
    if isinstance(value, Mapping):
        return {
            str(key): _public_projection(item)
            for key, item in value.items()
            if str(key).casefold() not in _PUBLIC_FORBIDDEN_KEYS
        }
    if isinstance(value, (list, tuple)):
        return [_public_projection(item) for item in value]
    return value


def _forbidden_paths(value: Any, path: str = "$") -> tuple[str, ...]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key)
            child = f"{path}.{key_text}"
            if key_text.casefold() in _PUBLIC_FORBIDDEN_KEYS:
                found.append(child)
            found.extend(_forbidden_paths(item, child))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            found.extend(_forbidden_paths(item, f"{path}[{index}]"))
    return tuple(sorted(set(found)))


def _enum_value(value: Any, enum_type: type[StrEnum], field: str) -> StrEnum:
    try:
        return enum_type(str(value))
    except ValueError as exc:
        raise ValidationError(f"{field} is not supported: {value}") from exc


@dataclass(frozen=True, slots=True)
class ReferenceTrackMetadata:
    """Required public declaration for one interval-track adapter."""

    adapter_id: str
    display_name: str
    version: str
    assembly: str
    track_type: str
    source_id: str
    source_version: str
    license: str
    access_mode: ReferenceAccessMode
    uri: str
    coordinate_system: CoordinateSystem
    supported_contexts: tuple[str, ...]
    channels: tuple[str, ...]
    limitations: tuple[str, ...]
    state: ReferenceArtifactState = ReferenceArtifactState.AVAILABLE
    schema_version: str = REFERENCE_TRACK_ADAPTER_ROW_SCHEMA_VERSION
    retrieval_policy: str = "bounded"
    max_records: int = REFERENCE_TRACK_ADAPTER_MAX_RECORDS
    max_query_limit: int = REFERENCE_TRACK_ADAPTER_MAX_QUERY_LIMIT
    documentation_url: str | None = None

    def __post_init__(self) -> None:
        for name in (
            "adapter_id",
            "display_name",
            "version",
            "assembly",
            "track_type",
            "source_id",
            "source_version",
            "license",
            "uri",
            "schema_version",
            "retrieval_policy",
        ):
            _text(getattr(self, name), name)
        object.__setattr__(
            self,
            "access_mode",
            _enum_value(self.access_mode, ReferenceAccessMode, "access_mode"),
        )
        object.__setattr__(
            self,
            "coordinate_system",
            _enum_value(self.coordinate_system, CoordinateSystem, "coordinate_system"),
        )
        object.__setattr__(
            self,
            "state",
            _enum_value(self.state, ReferenceArtifactState, "state"),
        )
        if not self.uri.startswith(("https://", "file://", "urn:")):
            raise ValidationError("reference adapter uri must be HTTPS, file, or URN")
        if (
            self.access_mode is ReferenceAccessMode.PUBLIC_HTTPS
            and not self.uri.startswith("https://")
        ):
            raise ValidationError("public_https adapters require an HTTPS URI")
        if self.documentation_url is not None and not self.documentation_url.startswith("https://"):
            raise ValidationError("documentation_url must be HTTPS when supplied")
        if self.max_records < 1 or self.max_records > REFERENCE_TRACK_ADAPTER_MAX_RECORDS:
            raise ValidationError("adapter max_records is outside the configured ceiling")
        if self.max_query_limit < 1 or self.max_query_limit > REFERENCE_TRACK_ADAPTER_MAX_QUERY_LIMIT:
            raise ValidationError("adapter max_query_limit is outside the configured ceiling")
        object.__setattr__(
            self,
            "supported_contexts",
            _unique_texts(self.supported_contexts, "supported_context"),
        )
        for context_pattern in self.supported_contexts:
            LatticeContext.from_key(context_pattern)
        object.__setattr__(self, "channels", _unique_texts(self.channels, "channel"))
        object.__setattr__(self, "limitations", _optional_texts(self.limitations))

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "ReferenceTrackMetadata":
        if not isinstance(raw, Mapping):
            raise ValidationError("reference track metadata must be an object")
        return cls(
            adapter_id=str(raw.get("adapter_id", "")),
            display_name=str(raw.get("display_name", "")),
            version=str(raw.get("version", "")),
            assembly=str(raw.get("assembly", "")),
            track_type=str(raw.get("track_type", "")),
            source_id=str(raw.get("source_id", "")),
            source_version=str(raw.get("source_version", "")),
            license=str(raw.get("license", "")),
            access_mode=ReferenceAccessMode(str(raw.get("access_mode", ""))),
            uri=str(raw.get("uri", "")),
            coordinate_system=CoordinateSystem(str(raw.get("coordinate_system", ""))),
            supported_contexts=tuple(str(item) for item in raw.get("supported_contexts", ())),
            channels=tuple(str(item) for item in raw.get("channels", ())),
            limitations=tuple(str(item) for item in raw.get("limitations", ())),
            state=ReferenceArtifactState(
                str(raw.get("state", ReferenceArtifactState.AVAILABLE.value))
            ),
            schema_version=str(
                raw.get("schema_version", REFERENCE_TRACK_ADAPTER_ROW_SCHEMA_VERSION)
            ),
            retrieval_policy=str(raw.get("retrieval_policy", "bounded")),
            max_records=int(raw.get("max_records", REFERENCE_TRACK_ADAPTER_MAX_RECORDS)),
            max_query_limit=int(
                raw.get("max_query_limit", REFERENCE_TRACK_ADAPTER_MAX_QUERY_LIMIT)
            ),
            documentation_url=(
                None
                if raw.get("documentation_url") is None
                else str(raw.get("documentation_url"))
            ),
        )

    @property
    def content_address(self) -> str:
        return content_hash(self.to_dict(), prefix="reference-track-metadata")

    @property
    def artifact_id(self) -> str:
        return f"track-adapter:{self.adapter_id}:{self.version}"

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)

    def to_artifact(self) -> ReferenceArtifact:
        notes = "; ".join(self.limitations) or "Adapter limitations were not supplied."
        return ReferenceArtifact(
            artifact_id=self.artifact_id,
            adapter_id=self.adapter_id,
            source_id=self.source_id,
            display_name=self.display_name,
            version=self.version,
            release=self.source_version,
            uri=self.uri,
            license=self.license,
            access_mode=self.access_mode,
            size_bytes=0,
            schema_version=self.schema_version,
            coordinate_system=self.coordinate_system.value,
            supported_contexts=self.supported_contexts,
            channels=self.channels,
            state=self.state,
            retrieval_policy=self.retrieval_policy,
            notes=notes,
        )


@dataclass(frozen=True, slots=True)
class ReferenceTrackReading:
    """One source-scoped, public-safe reading returned by an adapter."""

    adapter_id: str
    source_id: str
    source_version: str
    track_type: str
    record_id: str
    chromosome: str
    start: int
    end: int
    context_key: str
    state: str
    payload: Mapping[str, Any]
    tags: tuple[str, ...]
    raw_hash: str
    overlap_bp: int
    context_score: float
    specificity: int
    generalized_dimensions: tuple[str, ...]
    content_address: str

    @classmethod
    def from_match(
        cls,
        metadata: ReferenceTrackMetadata,
        match: Any,
    ) -> "ReferenceTrackReading":
        record = match.record
        body = {
            "adapter_id": metadata.adapter_id,
            "source_id": metadata.source_id,
            "source_version": metadata.source_version,
            "track_type": metadata.track_type,
            "record_id": record.record_id,
            "chromosome": record.chromosome,
            "start": record.start,
            "end": record.end,
            "context_key": record.context_key,
            "state": record.state,
            "payload": record.payload,
            "tags": record.tags,
            "raw_hash": record.raw_hash,
            "overlap_bp": match.overlap_bp,
            "context_score": match.context_score,
            "specificity": match.specificity,
            "generalized_dimensions": match.generalized_dimensions,
        }
        return cls(
            adapter_id=metadata.adapter_id,
            source_id=metadata.source_id,
            source_version=metadata.source_version,
            track_type=metadata.track_type,
            record_id=record.record_id,
            chromosome=record.chromosome,
            start=record.start,
            end=record.end,
            context_key=record.context_key,
            state=record.state,
            payload=dict(record.payload),
            tags=record.tags,
            raw_hash=record.raw_hash,
            overlap_bp=match.overlap_bp,
            context_score=match.context_score,
            specificity=match.specificity,
            generalized_dimensions=match.generalized_dimensions,
            content_address=content_hash(body, prefix="reference-track-reading"),
        )

    def __post_init__(self) -> None:
        for name in (
            "adapter_id",
            "source_id",
            "source_version",
            "track_type",
            "record_id",
            "chromosome",
            "context_key",
            "state",
            "raw_hash",
            "content_address",
        ):
            _text(getattr(self, name), name)
        if self.start < 1 or self.end < self.start:
            raise ValidationError("reference track reading interval is invalid")
        if self.overlap_bp < 1:
            raise ValidationError("reference track reading overlap_bp must be positive")
        if not 0.0 <= self.context_score <= 1.0:
            raise ValidationError("reference track reading context_score must be between 0 and 1")
        safe = _public_projection(dict(self.payload))
        object.__setattr__(self, "payload", dict(safe))
        expected = content_hash(self.body(), prefix="reference-track-reading")
        if self.content_address != expected:
            raise ValidationError("reference track reading content address does not match body")

    def body(self) -> dict[str, Any]:
        return {
            "adapter_id": self.adapter_id,
            "source_id": self.source_id,
            "source_version": self.source_version,
            "track_type": self.track_type,
            "record_id": self.record_id,
            "chromosome": self.chromosome,
            "start": self.start,
            "end": self.end,
            "context_key": self.context_key,
            "state": self.state,
            "payload": self.payload,
            "tags": self.tags,
            "raw_hash": self.raw_hash,
            "overlap_bp": self.overlap_bp,
            "context_score": self.context_score,
            "specificity": self.specificity,
            "generalized_dimensions": self.generalized_dimensions,
        }

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self.body() | {"content_address": self.content_address})


@dataclass(frozen=True, slots=True)
class ReferenceTrackQueryReport:
    """Adapter query result retaining index accounting and source metadata."""

    adapter_id: str
    metadata: ReferenceTrackMetadata
    metadata_address: str
    artifact_id: str
    query: ReferenceIndexQuery
    state: ReferenceTrackQueryState
    matches: tuple[ReferenceTrackReading, ...]
    interval_candidate_count: int
    rows_scanned: int
    context_rejected_count: int
    filter_rejected_count: int
    total_match_count: int
    offset: int
    limit: int
    truncated: bool
    warnings: tuple[str, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return self.state not in {
            ReferenceTrackQueryState.ABSTAINED,
            ReferenceTrackQueryState.INVALID,
        }

    def body(self) -> dict[str, Any]:
        return {
            "version": REFERENCE_TRACK_ADAPTER_VERSION,
            "adapter_id": self.adapter_id,
            "metadata": self.metadata,
            "metadata_address": self.metadata_address,
            "artifact_id": self.artifact_id,
            "query": self.query,
            "state": self.state,
            "matches": self.matches,
            "interval_candidate_count": self.interval_candidate_count,
            "rows_scanned": self.rows_scanned,
            "context_rejected_count": self.context_rejected_count,
            "filter_rejected_count": self.filter_rejected_count,
            "total_match_count": self.total_match_count,
            "offset": self.offset,
            "limit": self.limit,
            "truncated": self.truncated,
            "warnings": self.warnings,
        }

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self.body() | {"content_address": self.content_address, "accepted": self.accepted})


@dataclass(frozen=True, slots=True)
class ReferenceTrackAdapterBuildReport:
    """Build receipt for one declared adapter and its normalized index."""

    adapter: "DeclaredReferenceTrackAdapter"
    row_count: int
    accepted_count: int
    rejected_count: int
    warning_count: int
    error_count: int
    truncated: bool
    issues: tuple[ReferenceIndexBuildIssue, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return (
            not self.truncated
            and self.error_count == 0
            and self.adapter.state is ReferenceTrackAdapterState.ACCEPTED
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted": self.accepted}


@dataclass(frozen=True, slots=True)
class DeclaredReferenceTrackAdapter:
    """Immutable interval adapter bound to a declared source contract."""

    metadata: ReferenceTrackMetadata
    index: ReferenceIntervalIndex
    build_issues: tuple[ReferenceIndexBuildIssue, ...] = ()
    build_truncated: bool = False
    build_error_count: int = 0

    def __post_init__(self) -> None:
        if self.index.assembly != self.metadata.assembly:
            raise ValidationError(
                "reference track adapter assembly does not match its index assembly"
            )
        if self.build_error_count < 0:
            raise ValidationError("reference track adapter build_error_count cannot be negative")
        for row_index in range(self.index.record_count):
            record = self.index.record_at(row_index)
            if record.source_id != self.metadata.source_id:
                raise ValidationError(
                    f"reference row source_id does not match adapter source: {record.record_id}"
                )
            if record.track_type != self.metadata.track_type:
                raise ValidationError(
                    f"reference row track_type does not match adapter track: {record.record_id}"
                )

    @classmethod
    def from_rows(
        cls,
        metadata: ReferenceTrackMetadata,
        rows: Iterable[Mapping[str, Any] | PublicReferenceRecord],
        *,
        index_id: str | None = None,
        block_size: int = 256,
    ) -> ReferenceTrackAdapterBuildReport:
        prepared: list[Mapping[str, Any] | PublicReferenceRecord] = []
        for row in rows:
            if isinstance(row, PublicReferenceRecord):
                if row.source_id != metadata.source_id or row.track_type != metadata.track_type:
                    raise ValidationError(
                        f"typed reference row does not match adapter declaration: {row.record_id}"
                    )
                prepared.append(row)
                continue
            if not isinstance(row, Mapping):
                raise ValidationError("reference track adapter rows must be objects")
            normalized = dict(row)
            if normalized.get("source_id") is None or not str(
                normalized.get("source_id", "")
            ).strip():
                normalized["source_id"] = metadata.source_id
            if normalized.get("track_type") is None or not str(
                normalized.get("track_type", "")
            ).strip():
                normalized["track_type"] = metadata.track_type
            if normalized.get("state") is None or not str(normalized.get("state", "")).strip():
                normalized["state"] = "supported"
            prepared.append(normalized)
        build = build_reference_interval_index(
            prepared,
            index_id=index_id or metadata.adapter_id,
            assembly=metadata.assembly,
            max_records=metadata.max_records,
            block_size=block_size,
        )
        adapter = cls(
            metadata=metadata,
            index=build.index,
            build_issues=build.issues,
            build_truncated=build.truncated,
            build_error_count=build.error_count,
        )
        body = {
            "version": REFERENCE_TRACK_ADAPTER_VERSION,
            "adapter": adapter,
            "row_count": build.row_count,
            "accepted_count": build.accepted_count,
            "rejected_count": build.rejected_count,
            "warning_count": build.warning_count,
            "error_count": build.error_count,
            "truncated": build.truncated,
            "issues": build.issues,
        }
        return ReferenceTrackAdapterBuildReport(
            adapter=adapter,
            row_count=build.row_count,
            accepted_count=build.accepted_count,
            rejected_count=build.rejected_count,
            warning_count=build.warning_count,
            error_count=build.error_count,
            truncated=build.truncated,
            issues=build.issues,
            content_address=content_hash(body, prefix="reference-track-build"),
        )

    @property
    def metadata_address(self) -> str:
        return self.metadata.content_address

    @property
    def state(self) -> ReferenceTrackAdapterState:
        if self.metadata.state in {
            ReferenceArtifactState.QUARANTINED,
            ReferenceArtifactState.UNAVAILABLE,
        }:
            return ReferenceTrackAdapterState.ABSTAINED
        if (
            self.build_truncated
            or self.build_error_count
            or self.metadata.state
            in {ReferenceArtifactState.PROVISIONAL, ReferenceArtifactState.STALE}
        ):
            return ReferenceTrackAdapterState.REVIEW
        return ReferenceTrackAdapterState.ACCEPTED

    @property
    def content_address(self) -> str:
        return content_hash(self.body(), prefix="reference-track-adapter")

    @property
    def artifact(self) -> ReferenceArtifact:
        return self.metadata.to_artifact()

    def body(self) -> dict[str, Any]:
        return {
            "version": REFERENCE_TRACK_ADAPTER_VERSION,
            "metadata": self.metadata,
            "index": self.index,
            "build_issues": self.build_issues,
            "build_truncated": self.build_truncated,
            "build_error_count": self.build_error_count,
        }

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self.body() | {"state": self.state, "content_address": self.content_address})

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "DeclaredReferenceTrackAdapter":
        if not isinstance(raw, Mapping):
            raise ValidationError("reference track adapter must be an object")
        metadata = ReferenceTrackMetadata.from_dict(dict(raw.get("metadata", {})))
        index = ReferenceIntervalIndex.from_dict(dict(raw.get("index", {})))
        issues: list[ReferenceIndexBuildIssue] = []
        for item in raw.get("build_issues", ()):
            if not isinstance(item, Mapping):
                raise ValidationError("reference track build issue must be an object")
            issues.append(
                ReferenceIndexBuildIssue(
                    code=str(item.get("code", "")),
                    severity=str(item.get("severity", "error")),
                    message=str(item.get("message", "")),
                    row_number=None
                    if item.get("row_number") is None
                    else int(item.get("row_number")),
                    remediation=str(item.get("remediation", "")),
                )
            )
        adapter = cls(
            metadata=metadata,
            index=index,
            build_issues=tuple(issues),
            build_truncated=bool(raw.get("build_truncated", False)),
            build_error_count=int(raw.get("build_error_count", 0)),
        )
        supplied = str(raw.get("content_address", ""))
        if supplied and supplied != adapter.content_address:
            raise ValidationError("reference track adapter content address does not match body")
        if str(raw.get("metadata_address", metadata.content_address)) != metadata.content_address:
            raise ValidationError("reference track adapter metadata address does not match metadata")
        return adapter

    def _declares_context(self, context: LatticeContext) -> bool:
        if context.genome_build.casefold() != self.metadata.assembly.casefold():
            return False
        return any(
            match_context(pattern, context, mode=ContextQueryMode.LATTICE).accepted
            for pattern in self.metadata.supported_contexts
        )

    def _empty_report(
        self,
        query: ReferenceIndexQuery,
        state: ReferenceTrackQueryState,
        warning: str,
    ) -> ReferenceTrackQueryReport:
        body = {
            "version": REFERENCE_TRACK_ADAPTER_VERSION,
            "adapter_id": self.metadata.adapter_id,
            "metadata_address": self.metadata_address,
            "artifact_id": self.metadata.artifact_id,
            "query": query,
            "state": state,
            "matches": (),
            "interval_candidate_count": 0,
            "rows_scanned": 0,
            "context_rejected_count": 0,
            "filter_rejected_count": 0,
            "total_match_count": 0,
            "offset": query.offset,
            "limit": query.limit,
            "truncated": False,
            "warnings": (warning,),
        }
        return ReferenceTrackQueryReport(
            adapter_id=self.metadata.adapter_id,
            metadata=self.metadata,
            metadata_address=self.metadata_address,
            artifact_id=self.metadata.artifact_id,
            query=query,
            state=state,
            matches=(),
            interval_candidate_count=0,
            rows_scanned=0,
            context_rejected_count=0,
            filter_rejected_count=0,
            total_match_count=0,
            offset=query.offset,
            limit=query.limit,
            truncated=False,
            warnings=(warning,),
            content_address=content_hash(body, prefix="reference-track-query"),
        )

    def query(
        self,
        query: ReferenceIndexQuery | Mapping[str, Any],
    ) -> ReferenceTrackQueryReport:
        selected = (
            query
            if isinstance(query, ReferenceIndexQuery)
            else ReferenceIndexQuery.from_mapping(query)
        )
        if selected.limit > self.metadata.max_query_limit:
            raise ValidationError(
                f"query limit exceeds adapter limit {self.metadata.max_query_limit}"
            )
        if self.state is ReferenceTrackAdapterState.ABSTAINED:
            return self._empty_report(
                selected,
                ReferenceTrackQueryState.ABSTAINED,
                "adapter artifact is quarantined or unavailable; no reading was made",
            )
        if not self._declares_context(selected.context):
            return self._empty_report(
                selected,
                ReferenceTrackQueryState.OUT_OF_DOMAIN,
                "requested context is outside the adapter declaration",
            )
        result: ReferenceIndexQueryReport = self.index.query(selected)
        state_map = {
            ReferenceIndexQueryState.SUPPORTED: ReferenceTrackQueryState.SUPPORTED,
            ReferenceIndexQueryState.ABSENT: ReferenceTrackQueryState.ABSENT,
            ReferenceIndexQueryState.OUT_OF_DOMAIN: ReferenceTrackQueryState.OUT_OF_DOMAIN,
            ReferenceIndexQueryState.TRUNCATED: ReferenceTrackQueryState.TRUNCATED,
            ReferenceIndexQueryState.AMBIGUOUS: ReferenceTrackQueryState.OUT_OF_DOMAIN,
            ReferenceIndexQueryState.INVALID: ReferenceTrackQueryState.INVALID,
        }
        warnings = list(self.metadata.limitations)
        if self.metadata.state in {
            ReferenceArtifactState.PROVISIONAL,
            ReferenceArtifactState.STALE,
        }:
            warnings.append(f"adapter artifact state is {self.metadata.state.value}")
        warnings.extend(result.warnings)
        matches = tuple(
            ReferenceTrackReading.from_match(self.metadata, match) for match in result.matches
        )
        body = {
            "version": REFERENCE_TRACK_ADAPTER_VERSION,
            "adapter_id": self.metadata.adapter_id,
            "metadata_address": self.metadata_address,
            "artifact_id": self.metadata.artifact_id,
            "query": selected,
            "state": state_map[result.state],
            "matches": matches,
            "interval_candidate_count": result.interval_candidate_count,
            "rows_scanned": result.rows_scanned,
            "context_rejected_count": result.context_rejected_count,
            "filter_rejected_count": result.filter_rejected_count,
            "total_match_count": result.total_match_count,
            "offset": result.offset,
            "limit": result.limit,
            "truncated": result.truncated,
            "warnings": tuple(dict.fromkeys(warnings)),
        }
        return ReferenceTrackQueryReport(
            adapter_id=self.metadata.adapter_id,
            metadata=self.metadata,
            metadata_address=self.metadata_address,
            artifact_id=self.metadata.artifact_id,
            query=selected,
            state=state_map[result.state],
            matches=matches,
            interval_candidate_count=result.interval_candidate_count,
            rows_scanned=result.rows_scanned,
            context_rejected_count=result.context_rejected_count,
            filter_rejected_count=result.filter_rejected_count,
            total_match_count=result.total_match_count,
            offset=result.offset,
            limit=result.limit,
            truncated=result.truncated,
            warnings=tuple(dict.fromkeys(warnings)),
            content_address=content_hash(body, prefix="reference-track-query"),
        )


@dataclass(frozen=True, slots=True)
class ReferenceTrackProbe:
    """One bounded deterministic query used for adapter conformance."""

    probe_id: str
    query: ReferenceIndexQuery
    expected_state: ReferenceTrackQueryState | None = None

    def __post_init__(self) -> None:
        _text(self.probe_id, "probe_id")
        if self.expected_state is not None:
            object.__setattr__(
                self,
                "expected_state",
                _enum_value(
                    self.expected_state,
                    ReferenceTrackQueryState,
                    "expected_state",
                ),
            )

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any], *, index: ReferenceIntervalIndex | None = None) -> "ReferenceTrackProbe":
        if not isinstance(raw, Mapping):
            raise ValidationError("reference track probe must be an object")
        query_raw = raw.get("query", raw)
        if not isinstance(query_raw, Mapping):
            raise ValidationError("reference track probe query must be an object")
        return cls(
            probe_id=str(raw.get("probe_id", raw.get("id", ""))),
            query=ReferenceIndexQuery.from_mapping(query_raw),
            expected_state=(
                None
                if raw.get("expected_state") is None
                else ReferenceTrackQueryState(str(raw.get("expected_state")))
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceTrackConformanceCheck:
    """One independently addressable adapter conformance check."""

    category: ReferenceTrackConformanceCategory
    check_id: str
    accepted: bool
    detail: str
    observed: Any = None
    content_address: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "category",
            _enum_value(self.category, ReferenceTrackConformanceCategory, "category"),
        )
        _text(self.check_id, "check_id")
        _text(self.detail, "detail")
        expected = content_hash(
            {
                "category": self.category,
                "check_id": self.check_id,
                "accepted": self.accepted,
                "detail": self.detail,
                "observed": self.observed,
            },
            prefix="reference-track-conformance-check",
        )
        if self.content_address and self.content_address != expected:
            raise ValidationError("reference track conformance check address does not match body")
        object.__setattr__(self, "content_address", expected)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceTrackConformanceReport:
    """Deterministic adapter contract report with fail-closed state."""

    adapter_id: str
    adapter_address: str
    state: ReferenceTrackAdapterState
    checks: tuple[ReferenceTrackConformanceCheck, ...]
    probe_count: int
    content_address: str

    @property
    def accepted(self) -> bool:
        return self.state is ReferenceTrackAdapterState.ACCEPTED and all(
            check.accepted for check in self.checks
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "accepted": self.accepted,
            "passed_check_count": sum(check.accepted for check in self.checks),
            "failed_check_count": sum(not check.accepted for check in self.checks),
        }


def _check(
    category: ReferenceTrackConformanceCategory,
    check_id: str,
    accepted: bool,
    detail: str,
    observed: Any = None,
) -> ReferenceTrackConformanceCheck:
    return ReferenceTrackConformanceCheck(
        category=category,
        check_id=check_id,
        accepted=accepted,
        detail=detail,
        observed=observed,
    )


def conform_reference_track_adapter(
    adapter: DeclaredReferenceTrackAdapter,
    probes: Sequence[ReferenceTrackProbe] = (),
) -> ReferenceTrackConformanceReport:
    """Run metadata, artifact, round-trip, boundary, and deterministic probes."""

    selected_probes = tuple(probes)
    if len(selected_probes) > REFERENCE_TRACK_ADAPTER_MAX_PROBES:
        raise ValidationError("reference track conformance probe ceiling was exceeded")
    checks: list[ReferenceTrackConformanceCheck] = []
    metadata = adapter.metadata
    checks.append(
        _check(
            ReferenceTrackConformanceCategory.METADATA,
            "metadata-declared",
            bool(metadata.license and metadata.access_mode and metadata.supported_contexts),
            "license, access mode, contexts, channels, and coordinate system are declared",
            metadata.to_dict(),
        )
    )
    try:
        artifact = adapter.artifact
        artifact_ok = artifact.content_address == content_hash(
            artifact.body(), prefix="reference-artifact"
        )
        artifact_detail = "reference manifest artifact rebuilt and addressed"
    except (TypeError, ValueError, ValidationError) as exc:
        artifact = None
        artifact_ok = False
        artifact_detail = str(exc)
    checks.append(
        _check(
            ReferenceTrackConformanceCategory.ARTIFACT,
            "artifact-declared",
            artifact_ok,
            artifact_detail,
            artifact.to_dict() if artifact is not None else None,
        )
    )
    try:
        reopened = ReferenceIntervalIndex.from_dict(adapter.index.to_dict())
        index_ok = reopened.content_address == adapter.index.content_address
        index_detail = "columnar index round-tripped with the same address"
    except (TypeError, ValueError, ValidationError) as exc:
        reopened = None
        index_ok = False
        index_detail = str(exc)
    checks.append(
        _check(
            ReferenceTrackConformanceCategory.INDEX,
            "index-round-trip",
            index_ok,
            index_detail,
            adapter.index.content_address,
        )
    )
    public_values = {
        "metadata": metadata.to_dict(),
        "adapter": adapter.to_dict(),
        "artifact": artifact.to_dict() if artifact is not None else None,
    }
    forbidden = _forbidden_paths(public_values)
    checks.append(
        _check(
            ReferenceTrackConformanceCategory.PUBLIC_BOUNDARY,
            "public-boundary",
            not forbidden,
            "no forbidden attribution, credential, model, or direct-private paths are emitted",
            forbidden,
        )
    )
    checks.append(
        _check(
            ReferenceTrackConformanceCategory.INVOCATION,
            "probe-invocation",
            bool(selected_probes),
            "at least one bounded probe is required for release acceptance",
            len(selected_probes),
        )
    )
    if not metadata.limitations:
        checks.append(
            _check(
                ReferenceTrackConformanceCategory.METADATA,
                "limitations-declared",
                False,
                "adapter limitations must be declared before release",
            )
        )
    for probe in selected_probes:
        try:
            first = adapter.query(probe.query)
            second = adapter.query(probe.query)
            deterministic = first.to_dict() == second.to_dict()
            expected = (
                probe.expected_state is None or first.state is probe.expected_state
            )
            checks.append(
                _check(
                    ReferenceTrackConformanceCategory.DETERMINISM,
                    f"{probe.probe_id}:repeatable",
                    deterministic,
                    "repeated adapter queries returned identical public receipts",
                    first.content_address,
                )
            )
            checks.append(
                _check(
                    ReferenceTrackConformanceCategory.OUTPUT,
                    f"{probe.probe_id}:expected-state",
                    expected,
                    "probe state matches its declared expectation",
                    {
                        "expected": probe.expected_state,
                        "observed": first.state,
                    },
                )
            )
            output_forbidden = _forbidden_paths(first.to_dict())
            checks.append(
                _check(
                    ReferenceTrackConformanceCategory.PUBLIC_BOUNDARY,
                    f"{probe.probe_id}:output-boundary",
                    not output_forbidden,
                    "query output contains no forbidden public-boundary keys",
                    output_forbidden,
                )
            )
            checks.append(
                _check(
                    ReferenceTrackConformanceCategory.CONTEXT,
                    f"{probe.probe_id}:context",
                    first.state is not ReferenceTrackQueryState.INVALID,
                    "probe resolved through the declared context gate",
                    first.state,
                )
            )
        except (TypeError, ValueError, ValidationError) as exc:
            checks.append(
                _check(
                    ReferenceTrackConformanceCategory.OUTPUT,
                    f"{probe.probe_id}:exception",
                    False,
                    f"probe raised a validation error: {exc}",
                )
            )
    state = ReferenceTrackAdapterState.ACCEPTED
    if adapter.state is ReferenceTrackAdapterState.ABSTAINED:
        state = ReferenceTrackAdapterState.ABSTAINED
    elif adapter.state is not ReferenceTrackAdapterState.ACCEPTED:
        state = ReferenceTrackAdapterState.REVIEW
    elif any(
        not check.accepted
        for check in checks
        if check.category
        in {
            ReferenceTrackConformanceCategory.METADATA,
            ReferenceTrackConformanceCategory.ARTIFACT,
            ReferenceTrackConformanceCategory.INDEX,
            ReferenceTrackConformanceCategory.PUBLIC_BOUNDARY,
        }
    ):
        state = ReferenceTrackAdapterState.BLOCKED
    elif any(not check.accepted for check in checks):
        state = ReferenceTrackAdapterState.REVIEW
    body = {
        "version": REFERENCE_TRACK_ADAPTER_VERSION,
        "adapter_id": metadata.adapter_id,
        "adapter_address": adapter.content_address,
        "state": state,
        "checks": checks,
        "probe_count": len(selected_probes),
    }
    return ReferenceTrackConformanceReport(
        adapter_id=metadata.adapter_id,
        adapter_address=adapter.content_address,
        state=state,
        checks=tuple(checks),
        probe_count=len(selected_probes),
        content_address=content_hash(body, prefix="reference-track-conformance"),
    )


class ReferenceTrackAdapterRegistry:
    """Sorted registry for source-declared adapters used by atlas queries."""

    def __init__(self, adapters: Iterable[DeclaredReferenceTrackAdapter] = ()) -> None:
        self._adapters: dict[str, DeclaredReferenceTrackAdapter] = {}
        for adapter in adapters:
            self.register(adapter)

    def register(self, adapter: DeclaredReferenceTrackAdapter) -> None:
        adapter_id = adapter.metadata.adapter_id
        if adapter_id in self._adapters:
            raise ValidationError(f"reference track adapter already registered: {adapter_id}")
        if len(self._adapters) >= REFERENCE_TRACK_ADAPTER_MAX_ADAPTERS:
            raise ValidationError("reference track adapter registry ceiling was exceeded")
        self._adapters[adapter_id] = adapter

    def get(self, adapter_id: str) -> DeclaredReferenceTrackAdapter:
        try:
            return self._adapters[adapter_id]
        except KeyError as exc:
            raise ValidationError(f"reference track adapter is not registered: {adapter_id}") from exc

    def list(self) -> tuple[DeclaredReferenceTrackAdapter, ...]:
        return tuple(self._adapters[key] for key in sorted(self._adapters))

    def list_metadata(self) -> tuple[ReferenceTrackMetadata, ...]:
        return tuple(adapter.metadata for adapter in self.list())

    def query(
        self,
        adapter_id: str,
        query: ReferenceIndexQuery | Mapping[str, Any],
    ) -> ReferenceTrackQueryReport:
        return self.get(adapter_id).query(query)

    def query_all(
        self,
        query: ReferenceIndexQuery | Mapping[str, Any],
    ) -> tuple[ReferenceTrackQueryReport, ...]:
        return tuple(adapter.query(query) for adapter in self.list())

    def manifest(self, *, manifest_id: str = "reference-track-adapter-manifest"):
        from .reference_manifest import build_reference_manifest

        return build_reference_manifest(
            (adapter.artifact for adapter in self.list()),
            manifest_id=manifest_id,
            release_id=REFERENCE_TRACK_ADAPTER_VERSION,
            assembly=",".join(sorted({adapter.metadata.assembly for adapter in self.list()}))
            or "none",
        )

    def conformance(
        self,
        probes: Mapping[str, Sequence[ReferenceTrackProbe]] | None = None,
    ) -> tuple[ReferenceTrackConformanceReport, ...]:
        selected = probes or {}
        return tuple(
            conform_reference_track_adapter(adapter, selected.get(adapter.metadata.adapter_id, ()))
            for adapter in self.list()
        )

    def health(self) -> dict[str, Any]:
        state_counts: dict[str, int] = {}
        for adapter in self.list():
            state_counts[adapter.state.value] = state_counts.get(adapter.state.value, 0) + 1
        body = {
            "version": REFERENCE_TRACK_ADAPTER_VERSION,
            "count": len(self._adapters),
            "states": dict(sorted(state_counts.items())),
            "adapters": [
                {
                    "adapter_id": adapter.metadata.adapter_id,
                    "display_name": adapter.metadata.display_name,
                    "source_id": adapter.metadata.source_id,
                    "track_type": adapter.metadata.track_type,
                    "assembly": adapter.metadata.assembly,
                    "access_mode": adapter.metadata.access_mode,
                    "license": adapter.metadata.license,
                    "state": adapter.state,
                    "metadata_address": adapter.metadata_address,
                    "adapter_address": adapter.content_address,
                }
                for adapter in self.list()
            ],
        }
        return body | {"content_address": content_hash(body, prefix="reference-track-registry")}

    def to_dict(self) -> dict[str, Any]:
        body = {
            "version": REFERENCE_TRACK_ADAPTER_VERSION,
            "adapters": self.list(),
            "health": self.health(),
        }
        return jsonable(body | {"content_address": content_hash(body, prefix="reference-track-registry")})


def reference_track_adapter_schema() -> dict[str, Any]:
    """Return the versioned declaration, query, and conformance contract."""

    return {
        "version": REFERENCE_TRACK_ADAPTER_SCHEMA_VERSION,
        "adapter_version": REFERENCE_TRACK_ADAPTER_VERSION,
        "metadata_fields": [
            "adapter_id",
            "display_name",
            "version",
            "assembly",
            "track_type",
            "source_id",
            "source_version",
            "license",
            "access_mode",
            "uri",
            "coordinate_system",
            "supported_contexts",
            "channels",
            "limitations",
            "state",
            "schema_version",
            "retrieval_policy",
            "max_records",
            "max_query_limit",
            "documentation_url",
        ],
        "access_modes": [item.value for item in ReferenceAccessMode],
        "artifact_states": [item.value for item in ReferenceArtifactState],
        "coordinate_systems": [item.value for item in CoordinateSystem],
        "adapter_states": [item.value for item in ReferenceTrackAdapterState],
        "query_states": [item.value for item in ReferenceTrackQueryState],
        "conformance_categories": [item.value for item in ReferenceTrackConformanceCategory],
        "limits": {
            "max_adapters": REFERENCE_TRACK_ADAPTER_MAX_ADAPTERS,
            "max_records": REFERENCE_TRACK_ADAPTER_MAX_RECORDS,
            "max_probes": REFERENCE_TRACK_ADAPTER_MAX_PROBES,
            "max_query_limit": REFERENCE_TRACK_ADAPTER_MAX_QUERY_LIMIT,
        },
        "public_boundary": [
            "source, license, access mode, coordinate system, and limitations are required",
            "row payloads are recursively filtered before reading output",
            "query outputs retain adapter, source, version, context, and raw hashes",
            "unsupported and unavailable paths abstain without becoming negatives",
        ],
    }


def reference_track_adapter_capabilities() -> dict[str, Any]:
    """Describe adapter-backed atlas behavior without embedding source rows."""

    return {
        "version": REFERENCE_TRACK_ADAPTER_VERSION,
        "storage": "declared source metadata composed with a deterministic columnar interval index",
        "supported_inputs": ["JSON", "JSONL", "CSV", "TSV"],
        "query": {
            "coordinate_semantics": "one-based inclusive",
            "context_gate": "assembly and declared lattice patterns are checked before index selection",
            "ordering": "exact context, specificity, overlap, record ID, and source are deterministic",
            "negative_boundary": "absent and out_of_domain are distinct from abstained",
        },
        "release_gate": {
            "required": [
                "license",
                "access_mode",
                "coordinate_system",
                "supported_contexts",
                "limitations",
                "round_trip_address",
                "deterministic_probe",
            ],
            "states": [item.value for item in ReferenceTrackAdapterState],
        },
        "limits": reference_track_adapter_schema()["limits"],
    }


__all__ = [
    "DeclaredReferenceTrackAdapter",
    "REFERENCE_TRACK_ADAPTER_MAX_ADAPTERS",
    "REFERENCE_TRACK_ADAPTER_MAX_PROBES",
    "REFERENCE_TRACK_ADAPTER_MAX_QUERY_LIMIT",
    "REFERENCE_TRACK_ADAPTER_MAX_RECORDS",
    "REFERENCE_TRACK_ADAPTER_ROW_SCHEMA_VERSION",
    "REFERENCE_TRACK_ADAPTER_SCHEMA_VERSION",
    "REFERENCE_TRACK_ADAPTER_VERSION",
    "ReferenceTrackAdapterBuildReport",
    "ReferenceTrackAdapterRegistry",
    "ReferenceTrackAdapterState",
    "ReferenceTrackConformanceCategory",
    "ReferenceTrackConformanceCheck",
    "ReferenceTrackConformanceReport",
    "ReferenceTrackMetadata",
    "ReferenceTrackProbe",
    "ReferenceTrackQueryReport",
    "ReferenceTrackQueryState",
    "ReferenceTrackReading",
    "conform_reference_track_adapter",
    "reference_track_adapter_capabilities",
    "reference_track_adapter_schema",
]
