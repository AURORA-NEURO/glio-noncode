"""Bounded, content-addressed adapter contracts.

Adapters are an untrusted extension boundary. Registration snapshots metadata,
resolution binds every returned element to the adapter and variant that produced
it, and caller-configurable limits may only tighten hard process ceilings.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from pathlib import PurePosixPath
from threading import RLock
from typing import Any, Protocol, cast
from urllib.parse import urlsplit

from .errors import ValidationError
from .models import (
    CandidateElement,
    CaseManifest,
    EdgeType,
    EvidenceClaim,
    ReferenceContext,
    VariantIdentity,
)
from .serialization import canonical_bytes, content_hash, jsonable

ADAPTER_METADATA_VERSION = "adapter-metadata-v1"
ADAPTER_REGISTRY_VERSION = "adapter-registry-v1"
ADAPTER_RESOLUTION_VERSION = "adapter-resolution-v1"
ADAPTER_CLAIM_COLLECTION_VERSION = "adapter-claim-collection-v2"

ADAPTER_HARD_MAX_REGISTERED = 256
ADAPTER_HARD_MAX_SELECTED = 64
ADAPTER_HARD_MAX_VARIANTS = 10_000
ADAPTER_HARD_MAX_ELEMENTS_PER_VARIANT = 10_000
ADAPTER_HARD_MAX_ELEMENTS_TOTAL = 100_000
ADAPTER_HARD_MAX_CLAIMS_PER_ELEMENT = 10_000
ADAPTER_HARD_MAX_CLAIMS_TOTAL = 10_000
ADAPTER_HARD_MAX_ITEM_BYTES = 1 * 1024 * 1024
ADAPTER_HARD_MAX_MANIFEST_BYTES = 64 * 1024 * 1024
ADAPTER_HARD_MAX_REPORT_BYTES = 128 * 1024 * 1024

# Captured by AdapterLimits.__post_init__ at function-definition time so callers
# cannot relax enforcement by rebinding the public documentation constants.
_ADAPTER_LIMIT_CEILINGS = (
    ("max_registered_adapters", 256),
    ("max_selected_adapters", 64),
    ("max_variants", 10_000),
    ("max_elements_per_variant", 10_000),
    ("max_elements_total", 100_000),
    ("max_claims_per_element", 10_000),
    ("max_claims_total", 10_000),
    ("max_item_bytes", 1 * 1024 * 1024),
    ("max_manifest_bytes", 64 * 1024 * 1024),
    ("max_report_bytes", 128 * 1024 * 1024),
)
_HARD_REGISTRY_SNAPSHOT_ENTRIES = 256
_HARD_REGISTRY_SNAPSHOT_ENTRY_BYTES = 128 * 1024
_HARD_REGISTRY_SNAPSHOT_BYTES = 4 * 1024 * 1024
_HARD_RESOLUTION_ADAPTERS = 64
_HARD_RESOLUTION_VARIANTS = 10_000
_HARD_RESOLUTION_ITEMS = 100_000
_HARD_RESOLUTION_ITEM_BYTES = 1 * 1024 * 1024
_HARD_RESOLUTION_REPORT_BYTES = 128 * 1024 * 1024
_HARD_CLAIM_ATTRIBUTIONS = 100_000
_HARD_CLAIMS_PER_ATTRIBUTION = 10_000
_HARD_CLAIMS_TOTAL = 10_000
# An allowance map can cover every edge in a maximally valid evidence graph,
# even though collected adapter claims remain subject to the smaller total cap.
_HARD_CLAIM_EDGE_LIMIT_ENTRIES = 20_000
_HARD_CLAIM_BYTES = 1 * 1024 * 1024
_HARD_CLAIM_ATTRIBUTION_BYTES = 128 * 1024 * 1024
_HARD_CLAIM_REPORT_BYTES = 128 * 1024 * 1024

_MAX_ID_LENGTH = 128
_MAX_TEXT_LENGTH = 2_048
_MAX_DOCUMENTATION_URL_LENGTH = 2_048
_MAX_DECLARATIONS = 256
_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$")
_ADDRESS_PATTERN = re.compile(r"^[a-z][a-z0-9-]*:[0-9a-f]{64}$")
_VALIDATION_STATUSES = frozenset(
    {
        "unvalidated",
        "tested",
        "integration-tested",
        "validated",
        "deprecated",
        "quarantined",
    }
)


def _edge_id(source_id: str, target_id: str, edge_type: EdgeType) -> str:
    digest = content_hash(
        {"source": source_id, "target": target_id, "type": edge_type.value}
    ).split(":", 1)[1]
    return f"edge-{digest[:20]}"


def _resolution_item_edge_ids(
    variant_id: str,
    element: CandidateElement,
) -> frozenset[str]:
    """Return only hypothesis edges belonging to one adapter invocation."""

    gene_ids = element.target_genes or ("unresolved_gene",)
    state_ids = element.state_ids or ("unresolved_state",)
    state_source = gene_ids[0] if element.target_genes else element.element_id
    edges = {
        _edge_id(variant_id, element.element_id, EdgeType.VARIANT_TO_ELEMENT),
        *(_edge_id(element.element_id, gene_id, EdgeType.ELEMENT_TO_GENE) for gene_id in gene_ids),
        *(_edge_id(state_source, state_id, EdgeType.GENE_TO_STATE) for state_id in state_ids),
        _edge_id(
            variant_id,
            f"{element.element_id}:{gene_ids[0]}:{state_ids[0]}",
            EdgeType.CAUSAL_PATH,
        ),
    }
    return frozenset(edges)


def _integer(value: object, field_name: str, hard_maximum: int) -> int:
    if type(value) is not int or not 1 <= value <= hard_maximum:
        raise ValidationError(f"{field_name} must be an integer between 1 and {hard_maximum}")
    return value


def _text(value: object, field_name: str, *, maximum: int = _MAX_TEXT_LENGTH) -> str:
    if type(value) is not str:
        raise ValidationError(f"{field_name} must be a string")
    if value != value.strip() or not value:
        raise ValidationError(f"{field_name} must use non-empty canonical spelling")
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValidationError(f"{field_name} must be valid UTF-8") from exc
    if len(encoded) > maximum:
        raise ValidationError(f"{field_name} exceeds its byte ceiling")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValidationError(f"{field_name} contains control characters")
    return value


def _token(value: object, field_name: str) -> str:
    result = _text(value, field_name, maximum=_MAX_ID_LENGTH)
    if _TOKEN_PATTERN.fullmatch(result) is None:
        raise ValidationError(f"{field_name} must be a canonical identifier")
    return result


def _address(value: object, field_name: str, prefix: str | None = None) -> str:
    result = _text(value, field_name, maximum=160)
    if _ADDRESS_PATTERN.fullmatch(result) is None:
        raise ValidationError(f"{field_name} must be a canonical content address")
    if prefix is not None and not result.startswith(f"{prefix}:"):
        raise ValidationError(f"{field_name} must use the {prefix} namespace")
    return result


def _canonical_tuple(
    value: object,
    field_name: str,
    *,
    token: bool,
    required: bool,
) -> tuple[str, ...]:
    if type(value) is not tuple:
        raise ValidationError(f"{field_name} must be a tuple")
    if len(value) > _MAX_DECLARATIONS:
        raise ValidationError(f"{field_name} exceeds its item ceiling")
    validator = _token if token else _text
    result = tuple(validator(item, f"{field_name}[{index}]") for index, item in enumerate(value))
    if required and not result:
        raise ValidationError(f"{field_name} requires at least one value")
    if len(result) != len(set(result)):
        raise ValidationError(f"{field_name} must contain unique values")
    return tuple(sorted(result))


def _documentation_url(value: object) -> str | None:
    if value is None:
        return None
    result = _text(value, "documentation_url", maximum=_MAX_DOCUMENTATION_URL_LENGTH)
    if "\\" in result:
        raise ValidationError("documentation_url must use forward slashes")
    parsed = urlsplit(result)
    if parsed.scheme:
        if parsed.scheme != "https" or not parsed.hostname:
            raise ValidationError("documentation_url must use HTTPS")
        if parsed.username is not None or parsed.password is not None:
            raise ValidationError("documentation_url must not contain credentials")
        try:
            _ = parsed.port
        except ValueError as exc:
            raise ValidationError("documentation_url contains an invalid port") from exc
        if parsed.fragment:
            raise ValidationError("documentation_url must not contain a fragment")
        return result
    if parsed.netloc or parsed.query or parsed.fragment or result.startswith("/"):
        raise ValidationError("relative documentation_url must be a local path")
    path = PurePosixPath(result)
    if not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise ValidationError("relative documentation_url must be a canonical local path")
    return result


def _strict_mapping(
    value: object,
    field_name: str,
    expected_fields: frozenset[str],
) -> Mapping[str, Any]:
    if type(value) is not dict or any(type(key) is not str for key in value):
        raise ValidationError(f"{field_name} must be an object with string keys")
    if set(value) != expected_fields:
        missing = sorted(expected_fields - set(value))
        unknown = sorted(set(value) - expected_fields)
        raise ValidationError(
            f"{field_name} fields are not exact; missing={missing}, unknown={unknown}"
        )
    return value


def _bounded_bytes(value: object, field_name: str, maximum: int) -> bytes:
    try:
        result = canonical_bytes(value)
    except (TypeError, ValueError, OverflowError, UnicodeError, RecursionError) as exc:
        raise ValidationError(f"{field_name} is not canonical JSON") from exc
    if len(result) > maximum:
        raise ValidationError(f"{field_name} exceeds its byte ceiling")
    return result


def _optional_after_callback(value: object) -> Callable[[], None] | None:
    if value is None:
        return None
    if not callable(value):
        raise ValidationError("adapter after_callback must be callable")
    return cast(Callable[[], None], value)


def _snapshot_claim_limits_by_edge(value: object) -> dict[str, int] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise ValidationError("adapter max_claims_by_edge must be a mapping")
    try:
        item_count = len(value)
    except Exception as exc:
        raise ValidationError("adapter max_claims_by_edge could not be read") from exc
    if item_count > _HARD_CLAIM_EDGE_LIMIT_ENTRIES:
        raise ValidationError("adapter max_claims_by_edge exceeds its item ceiling")
    result: dict[str, int] = {}
    try:
        items = value.items()
        for index, (raw_edge_id, raw_maximum) in enumerate(items):
            if index >= _HARD_CLAIM_EDGE_LIMIT_ENTRIES:
                raise ValidationError("adapter max_claims_by_edge exceeds its item ceiling")
            edge_id = _token(raw_edge_id, "adapter max_claims_by_edge key")
            if edge_id in result:
                raise ValidationError("adapter max_claims_by_edge keys must be unique")
            if type(raw_maximum) is not int or not 0 <= raw_maximum <= _HARD_CLAIMS_TOTAL:
                raise ValidationError(
                    "adapter max_claims_by_edge values must be integers between 0 and "
                    f"{_HARD_CLAIMS_TOTAL}"
                )
            result[edge_id] = raw_maximum
    except ValidationError:
        raise
    except Exception as exc:
        raise ValidationError("adapter max_claims_by_edge could not be read") from exc
    if len(result) != item_count:
        raise ValidationError("adapter max_claims_by_edge changed while it was read")
    return result


@dataclass(frozen=True, slots=True)
class AdapterLimits:
    """Downward-only resource limits for one adapter registry."""

    max_registered_adapters: int = 64
    max_selected_adapters: int = 32
    max_variants: int = 1_000
    max_elements_per_variant: int = 5_000
    max_elements_total: int = 20_000
    max_claims_per_element: int = 2_000
    max_item_bytes: int = 256 * 1024
    max_manifest_bytes: int = 16 * 1024 * 1024
    max_report_bytes: int = 32 * 1024 * 1024
    max_claims_total: int = 10_000

    def __post_init__(
        self,
        _hard_ceilings: tuple[tuple[str, int], ...] = _ADAPTER_LIMIT_CEILINGS,
    ) -> None:
        for name, maximum in _hard_ceilings:
            _integer(getattr(self, name), f"adapter limits {name}", maximum)

    def to_dict(self) -> dict[str, int]:
        return {
            name: getattr(self, name)
            for name in (
                "max_registered_adapters",
                "max_selected_adapters",
                "max_variants",
                "max_elements_per_variant",
                "max_elements_total",
                "max_claims_per_element",
                "max_item_bytes",
                "max_manifest_bytes",
                "max_report_bytes",
                "max_claims_total",
            )
        }


@dataclass(frozen=True, slots=True)
class AdapterMetadata:
    """Canonical source and operational declarations for one adapter."""

    adapter_id: str
    display_name: str
    version: str
    license: str
    data_access: str
    supported_contexts: tuple[str, ...]
    channels: tuple[str, ...]
    failure_modes: tuple[str, ...]
    validation_status: str = "unvalidated"
    documentation_url: str | None = None
    source_ids: tuple[str, ...] = ()
    schema_version: str = ADAPTER_METADATA_VERSION
    content_address: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "adapter_id", _token(self.adapter_id, "adapter_id"))
        object.__setattr__(self, "display_name", _text(self.display_name, "display_name"))
        object.__setattr__(self, "version", _token(self.version, "version"))
        object.__setattr__(self, "license", _text(self.license, "license"))
        object.__setattr__(self, "data_access", _token(self.data_access, "data_access"))
        object.__setattr__(
            self,
            "supported_contexts",
            _canonical_tuple(
                self.supported_contexts,
                "supported_contexts",
                token=False,
                required=True,
            ),
        )
        object.__setattr__(
            self,
            "channels",
            _canonical_tuple(self.channels, "channels", token=True, required=True),
        )
        object.__setattr__(
            self,
            "failure_modes",
            _canonical_tuple(
                self.failure_modes,
                "failure_modes",
                token=True,
                required=True,
            ),
        )
        object.__setattr__(
            self,
            "source_ids",
            _canonical_tuple(self.source_ids, "source_ids", token=True, required=False),
        )
        status = _token(self.validation_status, "validation_status")
        if status not in _VALIDATION_STATUSES:
            raise ValidationError("validation_status is not supported")
        object.__setattr__(self, "validation_status", status)
        object.__setattr__(self, "documentation_url", _documentation_url(self.documentation_url))
        if self.schema_version != ADAPTER_METADATA_VERSION:
            raise ValidationError("adapter metadata schema version is not supported")
        expected = content_hash(self.body(), prefix="adapter-metadata")
        if self.content_address:
            _address(
                self.content_address,
                "adapter metadata content_address",
                "adapter-metadata",
            )
            if self.content_address != expected:
                raise ValidationError("adapter metadata content address does not match its body")
        object.__setattr__(self, "content_address", expected)

    def body(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "adapter_id": self.adapter_id,
            "display_name": self.display_name,
            "version": self.version,
            "license": self.license,
            "data_access": self.data_access,
            "supported_contexts": self.supported_contexts,
            "channels": self.channels,
            "failure_modes": self.failure_modes,
            "validation_status": self.validation_status,
            "documentation_url": self.documentation_url,
            "source_ids": self.source_ids,
        }

    def to_dict(self) -> dict[str, Any]:
        return cast(
            dict[str, Any],
            jsonable(self.body() | {"content_address": self.content_address}),
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> AdapterMetadata:
        fields = frozenset(
            {
                "schema_version",
                "adapter_id",
                "display_name",
                "version",
                "license",
                "data_access",
                "supported_contexts",
                "channels",
                "failure_modes",
                "validation_status",
                "documentation_url",
                "source_ids",
                "content_address",
            }
        )
        raw = _strict_mapping(value, "adapter metadata", fields)
        for sequence_name in (
            "supported_contexts",
            "channels",
            "failure_modes",
            "source_ids",
        ):
            if type(raw[sequence_name]) is not list:
                raise ValidationError(f"adapter metadata {sequence_name} must be an array")
        result = cls(
            adapter_id=raw["adapter_id"],
            display_name=raw["display_name"],
            version=raw["version"],
            license=raw["license"],
            data_access=raw["data_access"],
            supported_contexts=tuple(raw["supported_contexts"]),
            channels=tuple(raw["channels"]),
            failure_modes=tuple(raw["failure_modes"]),
            validation_status=raw["validation_status"],
            documentation_url=raw["documentation_url"],
            source_ids=tuple(raw["source_ids"]),
            schema_version=raw["schema_version"],
            content_address=raw["content_address"],
        )
        if canonical_bytes(value) != canonical_bytes(result.to_dict()):
            raise ValidationError("adapter metadata is not an exact canonical representation")
        return result


class EvidenceAdapter(Protocol):
    """Protocol for a source adapter that never mutates canonical state."""

    @property
    def metadata(self) -> AdapterMetadata: ...

    def resolve_elements(
        self,
        variant_id: str,
        context: ReferenceContext,
    ) -> tuple[CandidateElement, ...]: ...

    def collect_claims(
        self,
        variant_id: str,
        element_id: str,
        context: ReferenceContext,
    ) -> tuple[EvidenceClaim, ...]: ...


class VariantAwareEvidenceAdapter(EvidenceAdapter, Protocol):
    """Preferred adapter protocol receiving the complete typed variant."""

    def resolve_variant_elements(
        self,
        variant: VariantIdentity,
        context: ReferenceContext,
    ) -> tuple[CandidateElement, ...]: ...


def _validate_context(context: object) -> ReferenceContext:
    if type(context) is not ReferenceContext:
        raise ValidationError("adapter context must be an exact ReferenceContext")
    raw = context.to_dict()
    try:
        reopened = ReferenceContext.from_dict(raw, persisted=True)
    except (TypeError, ValueError, OverflowError, UnicodeError, RecursionError) as exc:
        raise ValidationError("adapter context is not canonical") from exc
    if canonical_bytes(raw) != canonical_bytes(reopened.to_dict()):
        raise ValidationError("adapter context is not an exact canonical representation")
    return reopened


def _validate_variant(variant: object) -> VariantIdentity:
    if type(variant) is not VariantIdentity:
        raise ValidationError("adapter variant must be an exact VariantIdentity")
    raw = variant.to_dict()
    try:
        reopened = VariantIdentity.from_dict(raw)
    except (TypeError, ValueError, OverflowError, UnicodeError, RecursionError) as exc:
        raise ValidationError("adapter variant is not canonical") from exc
    if canonical_bytes(raw) != canonical_bytes(reopened.to_dict()):
        raise ValidationError("adapter variant is not an exact canonical representation")
    return reopened


def _require_supported_context(
    metadata: AdapterMetadata,
    context: ReferenceContext,
) -> None:
    if (
        context.key not in metadata.supported_contexts
        and context.genome_build not in metadata.supported_contexts
    ):
        raise ValidationError(
            f"adapter does not support the requested context: {metadata.adapter_id}"
        )


def _validate_candidate_element(
    element: object,
    context: ReferenceContext,
    maximum_bytes: int,
) -> CandidateElement:
    if type(element) is not CandidateElement:
        raise ValidationError("adapter resolution items must be exact CandidateElement values")
    if type(element.context) is not ReferenceContext:
        raise ValidationError("adapter resolution item context must be an exact ReferenceContext")
    raw = element.to_dict()
    encoded = _bounded_bytes(raw, "adapter resolution item", maximum_bytes)
    try:
        reopened = CandidateElement.from_dict(raw, context)
    except (TypeError, ValueError, OverflowError, UnicodeError, RecursionError) as exc:
        raise ValidationError("adapter resolution item is not canonical") from exc
    if encoded != canonical_bytes(reopened.to_dict()):
        raise ValidationError("adapter resolution item is not an exact canonical representation")
    if element.context.key != context.key:
        raise ValidationError("adapter resolution item escaped the requested context")
    return reopened


def _validate_evidence_claim(
    claim: object,
    context: ReferenceContext,
    maximum_bytes: int,
) -> tuple[EvidenceClaim, int]:
    """Return a detached exact claim snapshot and its canonical byte size."""

    if type(claim) is not EvidenceClaim:
        raise ValidationError("adapter claim items must be exact EvidenceClaim values")
    try:
        raw = claim.to_dict()
    except (TypeError, ValueError, OverflowError, UnicodeError, RecursionError) as exc:
        raise ValidationError("adapter evidence claim is not canonical") from exc
    encoded = _bounded_bytes(raw, "adapter evidence claim", maximum_bytes)
    try:
        reopened = EvidenceClaim.from_dict(raw)
    except (TypeError, ValueError, OverflowError, UnicodeError, RecursionError) as exc:
        raise ValidationError("adapter evidence claim is not canonical") from exc
    if encoded != canonical_bytes(reopened.to_dict()):
        raise ValidationError("adapter evidence claim is not an exact canonical representation")
    if reopened.context != context:
        raise ValidationError("adapter evidence claim escaped the requested context")
    return reopened, len(encoded)


@dataclass(frozen=True, slots=True)
class StaticElementAdapter:
    """Fixture-friendly adapter backed by an immutable element collection."""

    metadata: AdapterMetadata
    elements: tuple[CandidateElement, ...] = ()

    def __post_init__(self) -> None:
        if type(self.metadata) is not AdapterMetadata:
            raise ValidationError("static adapter metadata must be exact AdapterMetadata")
        if type(self.elements) is not tuple:
            raise ValidationError("static adapter elements must be a tuple")
        if len(self.elements) > 100_000:
            raise ValidationError("static adapter elements exceed the hard ceiling")
        canonical: dict[str, bytes] = {}
        validated: list[CandidateElement] = []
        for element in self.elements:
            if (
                type(element) is not CandidateElement
                or type(element.context) is not ReferenceContext
            ):
                raise ValidationError(
                    "static adapter elements must be exact CandidateElement values"
                )
            _validate_context(element.context)
            canonical_element = _validate_candidate_element(
                element,
                element.context,
                1 * 1024 * 1024,
            )
            encoded = canonical_bytes(canonical_element.to_dict())
            previous = canonical.get(element.element_id)
            if previous is not None:
                if previous != encoded:
                    raise ValidationError(
                        f"static adapter has conflicting element identity: {element.element_id}"
                    )
                raise ValidationError(
                    f"static adapter has duplicate element identity: {element.element_id}"
                )
            canonical[element.element_id] = encoded
            validated.append(canonical_element)
        if not self.metadata.source_ids and validated:
            object.__setattr__(
                self,
                "metadata",
                replace(
                    self.metadata,
                    source_ids=tuple(sorted({item.source_id for item in validated})),
                    content_address="",
                ),
            )
        object.__setattr__(
            self,
            "elements",
            tuple(sorted(validated, key=lambda item: item.element_id)),
        )

    def resolve_elements(
        self, variant_id: str, context: ReferenceContext
    ) -> tuple[CandidateElement, ...]:
        _token(variant_id, "variant_id")
        canonical_context = _validate_context(context)
        _require_supported_context(self.metadata, canonical_context)
        return tuple(
            element for element in self.elements if element.context.key == canonical_context.key
        )

    def resolve_variant_elements(
        self,
        variant: VariantIdentity,
        context: ReferenceContext,
    ) -> tuple[CandidateElement, ...]:
        canonical_variant = _validate_variant(variant)
        canonical_context = _validate_context(context)
        _require_supported_context(self.metadata, canonical_context)
        if canonical_variant.genome_build != canonical_context.genome_build:
            raise ValidationError("adapter variant and context genome builds do not match")
        return self.resolve_elements(
            canonical_variant.variant_id,
            canonical_context,
        )

    def collect_claims(
        self, variant_id: str, element_id: str, context: ReferenceContext
    ) -> tuple[EvidenceClaim, ...]:
        _token(variant_id, "variant_id")
        _token(element_id, "element_id")
        canonical_context = _validate_context(context)
        _require_supported_context(self.metadata, canonical_context)
        return ()


@dataclass(frozen=True, slots=True)
class RegistryEntry:
    """A live registered adapter plus its detached metadata snapshot."""

    metadata: AdapterMetadata
    adapter: EvidenceAdapter = field(repr=False, compare=False)
    metadata_address: str = ""

    def __post_init__(self) -> None:
        if type(self.metadata) is not AdapterMetadata:
            raise ValidationError("registry entry metadata must be exact AdapterMetadata")
        expected = self.metadata.content_address
        if self.metadata_address and self.metadata_address != expected:
            raise ValidationError("registry entry metadata address does not match")
        object.__setattr__(self, "metadata_address", expected)


@dataclass(frozen=True, slots=True)
class AdapterRegistrySnapshotEntry:
    """Serializable registry entry without executable adapter state."""

    adapter_id: str
    version: str
    validation_status: str
    metadata_address: str
    source_ids: tuple[str, ...]
    channels: tuple[str, ...]

    def __post_init__(self) -> None:
        _token(self.adapter_id, "registry snapshot adapter_id")
        _token(self.version, "registry snapshot version")
        status = _token(
            self.validation_status,
            "registry snapshot validation_status",
        )
        if status not in _VALIDATION_STATUSES:
            raise ValidationError("registry snapshot validation_status is not supported")
        _address(
            self.metadata_address,
            "registry snapshot metadata_address",
            "adapter-metadata",
        )
        canonical_sources = _canonical_tuple(
            self.source_ids,
            "registry snapshot source_ids",
            token=True,
            required=False,
        )
        canonical_channels = _canonical_tuple(
            self.channels,
            "registry snapshot channels",
            token=True,
            required=True,
        )
        if canonical_sources != self.source_ids or canonical_channels != self.channels:
            raise ValidationError("registry snapshot declarations must be canonically ordered")
        _bounded_bytes(
            self.to_dict(),
            "adapter registry snapshot entry",
            _HARD_REGISTRY_SNAPSHOT_ENTRY_BYTES,
        )

    @classmethod
    def from_metadata(cls, metadata: AdapterMetadata) -> AdapterRegistrySnapshotEntry:
        return cls(
            adapter_id=metadata.adapter_id,
            version=metadata.version,
            validation_status=metadata.validation_status,
            metadata_address=metadata.content_address,
            source_ids=metadata.source_ids,
            channels=metadata.channels,
        )

    def to_dict(self) -> dict[str, Any]:
        return cast(dict[str, Any], jsonable(self))

    @classmethod
    def from_dict(
        cls,
        value: Mapping[str, Any],
    ) -> AdapterRegistrySnapshotEntry:
        fields = frozenset(
            {
                "adapter_id",
                "version",
                "validation_status",
                "metadata_address",
                "source_ids",
                "channels",
            }
        )
        raw = _strict_mapping(value, "adapter registry snapshot entry", fields)
        if type(raw["source_ids"]) is not list or type(raw["channels"]) is not list:
            raise ValidationError("adapter registry snapshot declarations must be arrays")
        if len(raw["source_ids"]) > _MAX_DECLARATIONS or len(raw["channels"]) > _MAX_DECLARATIONS:
            raise ValidationError(
                "adapter registry snapshot declarations exceed their item ceiling"
            )
        _bounded_bytes(
            raw,
            "adapter registry snapshot entry",
            _HARD_REGISTRY_SNAPSHOT_ENTRY_BYTES,
        )
        result = cls(
            adapter_id=raw["adapter_id"],
            version=raw["version"],
            validation_status=raw["validation_status"],
            metadata_address=raw["metadata_address"],
            source_ids=tuple(raw["source_ids"]),
            channels=tuple(raw["channels"]),
        )
        if canonical_bytes(raw) != canonical_bytes(result.to_dict()):
            raise ValidationError(
                "adapter registry snapshot entry is not an exact canonical representation"
            )
        return result


@dataclass(frozen=True, slots=True)
class AdapterRegistrySnapshot:
    """Atomic, deterministic public projection of one registry state."""

    adapters: tuple[AdapterRegistrySnapshotEntry, ...]
    version: str = ADAPTER_REGISTRY_VERSION
    content_address: str = ""

    def __post_init__(self) -> None:
        if self.version != ADAPTER_REGISTRY_VERSION:
            raise ValidationError("adapter registry snapshot version is not supported")
        if type(self.adapters) is not tuple:
            raise ValidationError("adapter registry snapshot entries are invalid")
        if len(self.adapters) > _HARD_REGISTRY_SNAPSHOT_ENTRIES:
            raise ValidationError("adapter registry snapshot exceeds its hard entry ceiling")
        if any(type(item) is not AdapterRegistrySnapshotEntry for item in self.adapters):
            raise ValidationError("adapter registry snapshot entries are invalid")
        ids = tuple(item.adapter_id for item in self.adapters)
        if ids != tuple(sorted(ids)) or len(ids) != len(set(ids)):
            raise ValidationError("adapter registry snapshot entries must be sorted and unique")
        expected = content_hash(self.body(), prefix="adapter-registry")
        if self.content_address:
            _address(
                self.content_address,
                "registry content_address",
                "adapter-registry",
            )
            if self.content_address != expected:
                raise ValidationError("adapter registry snapshot address does not match its body")
        object.__setattr__(self, "content_address", expected)
        _bounded_bytes(
            self.to_dict(),
            "adapter registry snapshot",
            _HARD_REGISTRY_SNAPSHOT_BYTES,
        )

    @property
    def count(self) -> int:
        return len(self.adapters)

    def body(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "count": self.count,
            "adapters": self.adapters,
        }

    def to_dict(self) -> dict[str, Any]:
        return cast(
            dict[str, Any],
            jsonable(self.body() | {"content_address": self.content_address}),
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> AdapterRegistrySnapshot:
        fields = frozenset({"version", "count", "adapters", "content_address"})
        raw = _strict_mapping(value, "adapter registry snapshot", fields)
        _bounded_bytes(
            raw,
            "adapter registry snapshot",
            _HARD_REGISTRY_SNAPSHOT_BYTES,
        )
        if type(raw["count"]) is not int or raw["count"] < 0:
            raise ValidationError("adapter registry snapshot count must be a non-negative integer")
        if type(raw["adapters"]) is not list:
            raise ValidationError("adapter registry snapshot adapters must be an array")
        if len(raw["adapters"]) > _HARD_REGISTRY_SNAPSHOT_ENTRIES:
            raise ValidationError("adapter registry snapshot exceeds its hard entry ceiling")
        entries = tuple(AdapterRegistrySnapshotEntry.from_dict(item) for item in raw["adapters"])
        result = cls(
            adapters=entries,
            version=raw["version"],
            content_address=raw["content_address"],
        )
        if raw["count"] != result.count:
            raise ValidationError("adapter registry snapshot count is not derived from its entries")
        if canonical_bytes(raw) != canonical_bytes(result.to_dict()):
            raise ValidationError(
                "adapter registry snapshot is not an exact canonical representation"
            )
        return result


@dataclass(frozen=True, slots=True)
class AdapterResolutionItem:
    """One element bound to the adapter metadata and variant invocation."""

    adapter_id: str
    metadata_address: str
    variant_id: str
    variant_address: str
    element: CandidateElement
    element_address: str = ""
    content_address: str = ""

    def __post_init__(self) -> None:
        _token(self.adapter_id, "resolution item adapter_id")
        _address(
            self.metadata_address,
            "resolution item metadata_address",
            "adapter-metadata",
        )
        _token(self.variant_id, "resolution item variant_id")
        _address(
            self.variant_address,
            "resolution item variant_address",
            "adapter-variant",
        )
        if (
            type(self.element) is not CandidateElement
            or type(self.element.context) is not ReferenceContext
        ):
            raise ValidationError("resolution item element must be exact CandidateElement")
        _validate_candidate_element(
            self.element,
            self.element.context,
            _HARD_RESOLUTION_ITEM_BYTES,
        )
        expected_element = content_hash(self.element.to_dict(), prefix="adapter-element")
        if self.element_address and self.element_address != expected_element:
            raise ValidationError("resolution item element address does not match")
        object.__setattr__(self, "element_address", expected_element)
        expected = content_hash(self.body(), prefix="adapter-resolution-item")
        if self.content_address:
            _address(
                self.content_address,
                "resolution item content_address",
                "adapter-resolution-item",
            )
            if self.content_address != expected:
                raise ValidationError("resolution item address does not match its body")
        object.__setattr__(self, "content_address", expected)
        _bounded_bytes(
            self.to_dict(),
            "adapter resolution item",
            _HARD_RESOLUTION_ITEM_BYTES,
        )

    @property
    def identity(self) -> tuple[str, str, str]:
        return self.adapter_id, self.variant_id, self.element.element_id

    def body(self) -> dict[str, Any]:
        return {
            "adapter_id": self.adapter_id,
            "metadata_address": self.metadata_address,
            "variant_id": self.variant_id,
            "variant_address": self.variant_address,
            "element": self.element,
            "element_address": self.element_address,
        }

    def to_dict(self) -> dict[str, Any]:
        return cast(
            dict[str, Any],
            jsonable(self.body() | {"content_address": self.content_address}),
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> AdapterResolutionItem:
        fields = frozenset(
            {
                "adapter_id",
                "metadata_address",
                "variant_id",
                "variant_address",
                "element",
                "element_address",
                "content_address",
            }
        )
        raw = _strict_mapping(value, "adapter resolution item", fields)
        _bounded_bytes(
            raw,
            "adapter resolution item",
            _HARD_RESOLUTION_ITEM_BYTES,
        )
        element_raw = raw["element"]
        if type(element_raw) is not dict:
            raise ValidationError("adapter resolution item element must be an object")
        context_raw = element_raw.get("context")
        if type(context_raw) is not dict:
            raise ValidationError("adapter resolution item element context must be an object")
        context = ReferenceContext.from_dict(context_raw, persisted=True)
        element = CandidateElement.from_dict(element_raw, context)
        _validate_candidate_element(
            element,
            context,
            _HARD_RESOLUTION_ITEM_BYTES,
        )
        result = cls(
            adapter_id=raw["adapter_id"],
            metadata_address=raw["metadata_address"],
            variant_id=raw["variant_id"],
            variant_address=raw["variant_address"],
            element=element,
            element_address=raw["element_address"],
            content_address=raw["content_address"],
        )
        if canonical_bytes(raw) != canonical_bytes(result.to_dict()):
            raise ValidationError(
                "adapter resolution item is not an exact canonical representation"
            )
        return result


@dataclass(frozen=True, slots=True)
class AdapterResolutionReport:
    """Content-addressed result of a bounded, atomic registry snapshot."""

    registry_address: str
    manifest_address: str
    context_address: str
    adapter_ids: tuple[str, ...]
    variant_ids: tuple[str, ...]
    items: tuple[AdapterResolutionItem, ...]
    version: str = ADAPTER_RESOLUTION_VERSION
    content_address: str = ""

    def __post_init__(self) -> None:
        if self.version != ADAPTER_RESOLUTION_VERSION:
            raise ValidationError("adapter resolution version is not supported")
        _address(
            self.registry_address,
            "resolution registry_address",
            "adapter-registry",
        )
        _address(
            self.manifest_address,
            "resolution manifest_address",
            "sha256",
        )
        _address(
            self.context_address,
            "resolution context_address",
            "adapter-context",
        )
        if type(self.adapter_ids) is not tuple:
            raise ValidationError("resolution adapter IDs must be a tuple")
        if len(self.adapter_ids) > _HARD_RESOLUTION_ADAPTERS:
            raise ValidationError("adapter resolution exceeds its hard adapter ceiling")
        for index, adapter_id in enumerate(self.adapter_ids):
            _token(adapter_id, f"resolution adapter_ids[{index}]")
        if tuple(sorted(self.adapter_ids)) != self.adapter_ids:
            raise ValidationError("resolution adapter IDs must be sorted")
        if len(self.adapter_ids) != len(set(self.adapter_ids)):
            raise ValidationError("resolution adapter IDs must be unique")
        if type(self.variant_ids) is not tuple:
            raise ValidationError("resolution variant IDs must be a tuple")
        if not self.variant_ids or len(self.variant_ids) > _HARD_RESOLUTION_VARIANTS:
            raise ValidationError("adapter resolution variant count is outside its hard bounds")
        for index, variant_id in enumerate(self.variant_ids):
            _token(variant_id, f"resolution variant_ids[{index}]")
        if tuple(sorted(self.variant_ids)) != self.variant_ids:
            raise ValidationError("resolution variant IDs must be sorted")
        if len(self.variant_ids) != len(set(self.variant_ids)):
            raise ValidationError("resolution variant IDs must be unique")
        if type(self.items) is not tuple:
            raise ValidationError("resolution report items are invalid")
        if len(self.items) > _HARD_RESOLUTION_ITEMS:
            raise ValidationError("adapter resolution exceeds its hard item ceiling")
        for item in self.items:
            if type(item) is not AdapterResolutionItem:
                raise ValidationError("resolution report items are invalid")
            AdapterResolutionItem.from_dict(item.to_dict())
        identities = tuple(item.identity for item in self.items)
        if identities != tuple(sorted(identities)) or len(identities) != len(set(identities)):
            raise ValidationError("resolution items must be sorted and uniquely attributed")
        if any(item.adapter_id not in self.adapter_ids for item in self.items):
            raise ValidationError("resolution item references an undeclared adapter")
        if any(item.variant_id not in self.variant_ids for item in self.items):
            raise ValidationError("resolution item references an undeclared variant")
        canonical_elements: dict[str, bytes] = {}
        for item in self.items:
            encoded = canonical_bytes(item.element.to_dict())
            previous = canonical_elements.setdefault(item.element.element_id, encoded)
            if previous != encoded:
                raise ValidationError(
                    "adapter resolution has conflicting element identity: "
                    f"{item.element.element_id}"
                )
        expected = content_hash(self.body(), prefix="adapter-resolution")
        if self.content_address:
            _address(
                self.content_address,
                "resolution content_address",
                "adapter-resolution",
            )
            if self.content_address != expected:
                raise ValidationError("adapter resolution address does not match its body")
        object.__setattr__(self, "content_address", expected)
        _bounded_bytes(
            self.to_dict(),
            "adapter resolution report",
            _HARD_RESOLUTION_REPORT_BYTES,
        )

    @property
    def elements(self) -> tuple[CandidateElement, ...]:
        by_id: dict[str, CandidateElement] = {}
        for item in self.items:
            by_id.setdefault(item.element.element_id, item.element)
        return tuple(by_id[key] for key in sorted(by_id))

    @property
    def element_count(self) -> int:
        return len(self.elements)

    @property
    def attribution_count(self) -> int:
        return len(self.items)

    def validate_manifest(self, manifest: CaseManifest) -> None:
        """Rebind every resolution item to one exact canonical base manifest."""

        if type(manifest) is not CaseManifest:
            raise ValidationError("adapter resolution manifest must be an exact CaseManifest")
        canonical_manifest = CaseManifest.from_dict(manifest.to_dict())
        variants = {variant.variant_id: variant for variant in canonical_manifest.variants}
        if (
            self.manifest_address != canonical_manifest.content_address
            or self.context_address
            != content_hash(canonical_manifest.context.to_dict(), prefix="adapter-context")
            or self.variant_ids != tuple(sorted(variants))
        ):
            raise ValidationError("adapter resolution does not bind its declared manifest")
        invocation_counts: dict[tuple[str, str], int] = {}
        for item in self.items:
            variant = variants.get(item.variant_id)
            if variant is None:
                raise ValidationError("adapter resolution item references an unknown variant")
            expected_variant_address = content_hash(
                variant.to_dict(),
                prefix="adapter-variant",
            )
            if item.variant_address != expected_variant_address:
                raise ValidationError(
                    "adapter resolution item variant address does not match the manifest"
                )
            # Candidate elements are context-compatible by their stable context
            # key.  Source-version detail belongs to the element's own
            # provenance and need not be byte-identical to the case context.
            if item.element.context.key != canonical_manifest.context.key:
                raise ValidationError("adapter resolution item escaped the manifest context")
            invocation = item.adapter_id, item.variant_id
            invocation_counts[invocation] = invocation_counts.get(invocation, 0) + 1
            if invocation_counts[invocation] > ADAPTER_HARD_MAX_ELEMENTS_PER_VARIANT:
                raise ValidationError(
                    "adapter resolution exceeds its hard per-invocation item ceiling"
                )

    def body(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "registry_address": self.registry_address,
            "manifest_address": self.manifest_address,
            "context_address": self.context_address,
            "adapter_ids": self.adapter_ids,
            "variant_ids": self.variant_ids,
            "items": self.items,
        }

    def to_dict(self) -> dict[str, Any]:
        return cast(
            dict[str, Any],
            jsonable(self.body() | {"content_address": self.content_address})
            | {
                "element_count": self.element_count,
                "attribution_count": self.attribution_count,
            },
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> AdapterResolutionReport:
        fields = frozenset(
            {
                "version",
                "registry_address",
                "manifest_address",
                "context_address",
                "adapter_ids",
                "variant_ids",
                "items",
                "content_address",
                "element_count",
                "attribution_count",
            }
        )
        raw = _strict_mapping(value, "adapter resolution report", fields)
        _bounded_bytes(
            raw,
            "adapter resolution report",
            _HARD_RESOLUTION_REPORT_BYTES,
        )
        for field_name in ("adapter_ids", "variant_ids", "items"):
            if type(raw[field_name]) is not list:
                raise ValidationError(f"adapter resolution report {field_name} must be an array")
        if len(raw["adapter_ids"]) > _HARD_RESOLUTION_ADAPTERS:
            raise ValidationError("adapter resolution exceeds its hard adapter ceiling")
        if not raw["variant_ids"] or len(raw["variant_ids"]) > _HARD_RESOLUTION_VARIANTS:
            raise ValidationError("adapter resolution variant count is outside its hard bounds")
        if len(raw["items"]) > _HARD_RESOLUTION_ITEMS:
            raise ValidationError("adapter resolution exceeds its hard item ceiling")
        for field_name in ("element_count", "attribution_count"):
            count = raw[field_name]
            if type(count) is not int or count < 0:
                raise ValidationError(
                    f"adapter resolution {field_name} must be a non-negative integer"
                )
        items = tuple(AdapterResolutionItem.from_dict(item) for item in raw["items"])
        result = cls(
            registry_address=raw["registry_address"],
            manifest_address=raw["manifest_address"],
            context_address=raw["context_address"],
            adapter_ids=tuple(raw["adapter_ids"]),
            variant_ids=tuple(raw["variant_ids"]),
            items=items,
            version=raw["version"],
            content_address=raw["content_address"],
        )
        if raw["element_count"] != result.element_count:
            raise ValidationError("adapter resolution element_count is not derived from its items")
        if raw["attribution_count"] != result.attribution_count:
            raise ValidationError(
                "adapter resolution attribution_count is not derived from its items"
            )
        if canonical_bytes(raw) != canonical_bytes(result.to_dict()):
            raise ValidationError(
                "adapter resolution report is not an exact canonical representation"
            )
        return result


@dataclass(frozen=True, slots=True)
class AdapterClaimAttribution:
    """Claims from one exact adapter, variant, and resolved-element invocation."""

    adapter_id: str
    metadata_address: str
    variant_id: str
    variant_address: str
    element_id: str
    element_address: str
    resolution_item_address: str
    claims: tuple[EvidenceClaim, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        _token(self.adapter_id, "claim attribution adapter_id")
        _address(
            self.metadata_address,
            "claim attribution metadata_address",
            "adapter-metadata",
        )
        _token(self.variant_id, "claim attribution variant_id")
        _address(
            self.variant_address,
            "claim attribution variant_address",
            "adapter-variant",
        )
        _token(self.element_id, "claim attribution element_id")
        _address(
            self.element_address,
            "claim attribution element_address",
            "adapter-element",
        )
        _address(
            self.resolution_item_address,
            "claim attribution resolution_item_address",
            "adapter-resolution-item",
        )
        if type(self.claims) is not tuple:
            raise ValidationError("claim attribution claims must be a tuple")
        if len(self.claims) > _HARD_CLAIMS_PER_ATTRIBUTION:
            raise ValidationError("claim attribution exceeds its hard claim ceiling")
        validated: list[EvidenceClaim] = []
        for claim in self.claims:
            if type(claim) is not EvidenceClaim or type(claim.context) is not ReferenceContext:
                raise ValidationError("claim attribution items must be exact EvidenceClaim values")
            canonical_context = _validate_context(claim.context)
            reopened, _ = _validate_evidence_claim(
                claim,
                canonical_context,
                _HARD_CLAIM_BYTES,
            )
            validated.append(reopened)
        claim_ids = tuple(claim.evidence_id for claim in validated)
        if len(claim_ids) != len(set(claim_ids)):
            raise ValidationError("claim attribution claim IDs must be unique")
        object.__setattr__(self, "claims", tuple(validated))
        expected = content_hash(self.body(), prefix="adapter-claim-attribution")
        if self.content_address:
            _address(
                self.content_address,
                "claim attribution content_address",
                "adapter-claim-attribution",
            )
            if self.content_address != expected:
                raise ValidationError("claim attribution address does not match its body")
        object.__setattr__(self, "content_address", expected)
        _bounded_bytes(
            self.to_dict(),
            "adapter claim attribution",
            _HARD_CLAIM_ATTRIBUTION_BYTES,
        )

    @property
    def identity(self) -> tuple[str, str, str]:
        return self.adapter_id, self.variant_id, self.element_id

    @property
    def claim_count(self) -> int:
        return len(self.claims)

    def body(self) -> dict[str, Any]:
        return {
            "adapter_id": self.adapter_id,
            "metadata_address": self.metadata_address,
            "variant_id": self.variant_id,
            "variant_address": self.variant_address,
            "element_id": self.element_id,
            "element_address": self.element_address,
            "resolution_item_address": self.resolution_item_address,
            "claims": self.claims,
        }

    def to_dict(self) -> dict[str, Any]:
        return cast(
            dict[str, Any],
            jsonable(self.body() | {"content_address": self.content_address})
            | {"claim_count": self.claim_count},
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> AdapterClaimAttribution:
        fields = frozenset(
            {
                "adapter_id",
                "metadata_address",
                "variant_id",
                "variant_address",
                "element_id",
                "element_address",
                "resolution_item_address",
                "claims",
                "content_address",
                "claim_count",
            }
        )
        raw = _strict_mapping(value, "adapter claim attribution", fields)
        _bounded_bytes(
            raw,
            "adapter claim attribution",
            _HARD_CLAIM_ATTRIBUTION_BYTES,
        )
        if type(raw["claims"]) is not list:
            raise ValidationError("adapter claim attribution claims must be an array")
        if len(raw["claims"]) > _HARD_CLAIMS_PER_ATTRIBUTION:
            raise ValidationError("claim attribution exceeds its hard claim ceiling")
        if type(raw["claim_count"]) is not int or raw["claim_count"] < 0:
            raise ValidationError(
                "adapter claim attribution claim_count must be a non-negative integer"
            )
        claims = tuple(EvidenceClaim.from_dict(item) for item in raw["claims"])
        result = cls(
            adapter_id=raw["adapter_id"],
            metadata_address=raw["metadata_address"],
            variant_id=raw["variant_id"],
            variant_address=raw["variant_address"],
            element_id=raw["element_id"],
            element_address=raw["element_address"],
            resolution_item_address=raw["resolution_item_address"],
            claims=claims,
            content_address=raw["content_address"],
        )
        if raw["claim_count"] != result.claim_count:
            raise ValidationError(
                "adapter claim attribution claim_count is not derived from its claims"
            )
        if canonical_bytes(raw) != canonical_bytes(result.to_dict()):
            raise ValidationError(
                "adapter claim attribution is not an exact canonical representation"
            )
        return result


@dataclass(frozen=True, slots=True)
class AdapterClaimCollectionReport:
    """Addressed, replayable claim collection bound to one resolution report."""

    registry_snapshot: AdapterRegistrySnapshot
    adapter_metadata: tuple[AdapterMetadata, ...]
    manifest_address: str
    context: ReferenceContext
    adapter_ids: tuple[str, ...]
    variant_ids: tuple[str, ...]
    resolution_address: str
    attributions: tuple[AdapterClaimAttribution, ...]
    registry_address: str = ""
    context_address: str = ""
    version: str = ADAPTER_CLAIM_COLLECTION_VERSION
    content_address: str = ""

    def __post_init__(self) -> None:
        if self.version != ADAPTER_CLAIM_COLLECTION_VERSION:
            raise ValidationError("adapter claim collection version is not supported")
        if type(self.registry_snapshot) is not AdapterRegistrySnapshot:
            raise ValidationError(
                "claim collection registry snapshot must be exact AdapterRegistrySnapshot"
            )
        canonical_snapshot = AdapterRegistrySnapshot.from_dict(self.registry_snapshot.to_dict())
        object.__setattr__(self, "registry_snapshot", canonical_snapshot)
        expected_registry_address = canonical_snapshot.content_address
        if self.registry_address:
            _address(
                self.registry_address,
                "claim collection registry_address",
                "adapter-registry",
            )
            if self.registry_address != expected_registry_address:
                raise ValidationError(
                    "claim collection registry address does not match its snapshot"
                )
        object.__setattr__(self, "registry_address", expected_registry_address)
        _address(
            self.manifest_address,
            "claim collection manifest_address",
            "sha256",
        )
        canonical_context = _validate_context(self.context)
        canonical_context = ReferenceContext.from_dict(
            canonical_context.to_dict(),
            persisted=True,
        )
        object.__setattr__(self, "context", canonical_context)
        expected_context_address = content_hash(
            canonical_context.to_dict(),
            prefix="adapter-context",
        )
        if self.context_address:
            _address(
                self.context_address,
                "claim collection context_address",
                "adapter-context",
            )
            if self.context_address != expected_context_address:
                raise ValidationError("claim collection context address does not match its context")
        object.__setattr__(self, "context_address", expected_context_address)
        _address(
            self.resolution_address,
            "claim collection resolution_address",
            "adapter-resolution",
        )
        for field_name, values, hard_maximum, required in (
            (
                "adapter_ids",
                self.adapter_ids,
                _HARD_RESOLUTION_ADAPTERS,
                False,
            ),
            (
                "variant_ids",
                self.variant_ids,
                _HARD_RESOLUTION_VARIANTS,
                True,
            ),
        ):
            if type(values) is not tuple:
                raise ValidationError(f"claim collection {field_name} must be a tuple")
            if (required and not values) or len(values) > hard_maximum:
                raise ValidationError(
                    f"claim collection {field_name} count is outside its hard bounds"
                )
            for index, value in enumerate(values):
                _token(value, f"claim collection {field_name}[{index}]")
            if values != tuple(sorted(values)) or len(values) != len(set(values)):
                raise ValidationError(f"claim collection {field_name} must be sorted and unique")
        snapshot_by_id = {entry.adapter_id: entry for entry in canonical_snapshot.adapters}
        if tuple(snapshot_by_id) != self.adapter_ids:
            raise ValidationError(
                "claim collection registry snapshot must exactly cover selected adapter IDs"
            )
        if type(self.adapter_metadata) is not tuple:
            raise ValidationError("claim collection adapter metadata must be a tuple")
        if len(self.adapter_metadata) > _HARD_RESOLUTION_ADAPTERS:
            raise ValidationError("claim collection adapter metadata exceeds its hard ceiling")
        canonical_metadata: list[AdapterMetadata] = []
        for metadata in self.adapter_metadata:
            if type(metadata) is not AdapterMetadata:
                raise ValidationError(
                    "claim collection adapter metadata must contain exact AdapterMetadata values"
                )
            canonical_metadata.append(AdapterMetadata.from_dict(metadata.to_dict()))
        metadata_ids = tuple(metadata.adapter_id for metadata in canonical_metadata)
        if metadata_ids != self.adapter_ids:
            raise ValidationError(
                "claim collection adapter metadata must exactly cover selected adapter IDs"
            )
        metadata_by_id = {metadata.adapter_id: metadata for metadata in canonical_metadata}
        for metadata in canonical_metadata:
            if (
                AdapterRegistrySnapshotEntry.from_metadata(metadata)
                != snapshot_by_id[metadata.adapter_id]
            ):
                raise ValidationError(
                    "claim collection adapter metadata does not reproduce its registry projection"
                )
            _require_supported_context(metadata, canonical_context)
        object.__setattr__(self, "adapter_metadata", tuple(canonical_metadata))
        if type(self.attributions) is not tuple:
            raise ValidationError("claim collection attributions must be a tuple")
        if len(self.attributions) > _HARD_CLAIM_ATTRIBUTIONS:
            raise ValidationError("claim collection exceeds its hard attribution ceiling")
        canonical_attributions: list[AdapterClaimAttribution] = []
        for attribution in self.attributions:
            if type(attribution) is not AdapterClaimAttribution:
                raise ValidationError(
                    "claim collection items must be exact AdapterClaimAttribution values"
                )
            canonical_attributions.append(AdapterClaimAttribution.from_dict(attribution.to_dict()))
        identities = tuple(item.identity for item in canonical_attributions)
        if identities != tuple(sorted(identities)) or len(identities) != len(set(identities)):
            raise ValidationError(
                "claim collection attributions must be sorted and uniquely identified"
            )
        resolution_items = tuple(item.resolution_item_address for item in canonical_attributions)
        if len(resolution_items) != len(set(resolution_items)):
            raise ValidationError("claim collection resolution item addresses must be unique")
        all_claim_ids: list[str] = []
        for attribution in canonical_attributions:
            if attribution.adapter_id not in self.adapter_ids:
                raise ValidationError(
                    "claim collection attribution references an undeclared adapter"
                )
            if attribution.variant_id not in self.variant_ids:
                raise ValidationError(
                    "claim collection attribution references an undeclared variant"
                )
            metadata = metadata_by_id[attribution.adapter_id]
            if attribution.metadata_address != metadata.content_address:
                raise ValidationError(
                    "claim collection attribution metadata address does not match its snapshot"
                )
            for claim in attribution.claims:
                if claim.context != canonical_context:
                    raise ValidationError("claim collection evidence escaped the requested context")
                if claim.produced_by != attribution.adapter_id:
                    raise ValidationError(
                        "claim collection evidence producer does not match its adapter attribution"
                    )
                if claim.source_id not in metadata.source_ids:
                    raise ValidationError(
                        "claim collection evidence escaped declared adapter sources"
                    )
                if claim.channel not in metadata.channels:
                    raise ValidationError(
                        "claim collection evidence escaped declared adapter channels"
                    )
                all_claim_ids.append(claim.evidence_id)
        if len(all_claim_ids) > _HARD_CLAIMS_TOTAL:
            raise ValidationError("claim collection exceeds its hard total claim ceiling")
        if len(all_claim_ids) != len(set(all_claim_ids)):
            raise ValidationError("claim collection evidence IDs must be globally unique")
        claim_positions = {evidence_id: index for index, evidence_id in enumerate(all_claim_ids)}
        flattened_claims = tuple(
            claim for attribution in canonical_attributions for claim in attribution.claims
        )
        claims_by_id = {claim.evidence_id: claim for claim in flattened_claims}
        for claim in flattened_claims:
            position = claim_positions[claim.evidence_id]
            for dependency in claim.depends_on:
                dependency_position = claim_positions.get(dependency)
                if dependency_position is None:
                    _address(
                        dependency,
                        f"claim collection dependency for {claim.evidence_id}",
                    )
                elif dependency_position >= position:
                    raise ValidationError(
                        "claim collection evidence contains a forward or cyclic dependency"
                    )
            if claim.supersedes is not None:
                superseded_position = claim_positions.get(claim.supersedes)
                if superseded_position is None or superseded_position >= position:
                    raise ValidationError(
                        "claim collection evidence must supersede an earlier collected claim"
                    )
                if claims_by_id[claim.supersedes].edge_id != claim.edge_id:
                    raise ValidationError(
                        "claim collection evidence cannot supersede a claim on another edge"
                    )
        object.__setattr__(self, "attributions", tuple(canonical_attributions))
        expected = content_hash(self.body(), prefix="adapter-claim-collection")
        if self.content_address:
            _address(
                self.content_address,
                "claim collection content_address",
                "adapter-claim-collection",
            )
            if self.content_address != expected:
                raise ValidationError("claim collection address does not match its body")
        object.__setattr__(self, "content_address", expected)
        _bounded_bytes(
            self.to_dict(),
            "adapter claim collection report",
            _HARD_CLAIM_REPORT_BYTES,
        )

    @property
    def attribution_count(self) -> int:
        return len(self.attributions)

    @property
    def claims(self) -> tuple[EvidenceClaim, ...]:
        return tuple(claim for attribution in self.attributions for claim in attribution.claims)

    @property
    def claim_count(self) -> int:
        return len(self.claims)

    def validate_resolution(self, resolution: AdapterResolutionReport) -> None:
        """Require one exact attribution for every resolved adapter invocation."""

        if type(resolution) is not AdapterResolutionReport:
            raise ValidationError(
                "claim collection resolution must be an exact AdapterResolutionReport"
            )
        canonical = AdapterResolutionReport.from_dict(resolution.to_dict())
        if (
            self.resolution_address != canonical.content_address
            or self.registry_address != canonical.registry_address
            or self.manifest_address != canonical.manifest_address
            or self.context_address != canonical.context_address
            or self.adapter_ids != canonical.adapter_ids
            or self.variant_ids != canonical.variant_ids
        ):
            raise ValidationError("claim collection does not close over its declared resolution")
        attribution_addresses = tuple(
            attribution.resolution_item_address for attribution in self.attributions
        )
        resolution_addresses = tuple(item.content_address for item in canonical.items)
        if attribution_addresses != resolution_addresses:
            raise ValidationError(
                "claim collection must attribute every resolution item exactly once"
            )
        metadata_by_id = {metadata.adapter_id: metadata for metadata in self.adapter_metadata}
        for attribution, item in zip(self.attributions, canonical.items, strict=True):
            if (
                attribution.adapter_id != item.adapter_id
                or attribution.metadata_address != item.metadata_address
                or attribution.variant_id != item.variant_id
                or attribution.variant_address != item.variant_address
                or attribution.element_id != item.element.element_id
                or attribution.element_address != item.element_address
            ):
                raise ValidationError("claim attribution does not match its exact resolution item")
            metadata = metadata_by_id[item.adapter_id]
            if item.element.source_id not in metadata.source_ids:
                raise ValidationError(
                    "adapter resolution element escaped its selected metadata sources"
                )

    def validate_claim_ownership(self, resolution: AdapterResolutionReport) -> None:
        """Require each claim edge to belong to its attributed resolution item.

        Factorized gene-to-state edges can intentionally belong to more than one
        item; attribution constrains membership rather than claiming exclusivity.
        """

        self.validate_resolution(resolution)
        canonical = AdapterResolutionReport.from_dict(resolution.to_dict())
        for attribution, item in zip(self.attributions, canonical.items, strict=True):
            allowed_edges = _resolution_item_edge_ids(item.variant_id, item.element)
            if any(claim.edge_id not in allowed_edges for claim in attribution.claims):
                raise ValidationError(
                    "adapter claim edge does not belong to its attributed resolution item"
                )

    def body(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "registry_snapshot": self.registry_snapshot.to_dict(),
            "adapter_metadata": tuple(item.to_dict() for item in self.adapter_metadata),
            "registry_address": self.registry_address,
            "manifest_address": self.manifest_address,
            "context": self.context.to_dict(),
            "context_address": self.context_address,
            "adapter_ids": self.adapter_ids,
            "variant_ids": self.variant_ids,
            "resolution_address": self.resolution_address,
            "attributions": tuple(item.to_dict() for item in self.attributions),
        }

    def to_dict(self) -> dict[str, Any]:
        return cast(
            dict[str, Any],
            jsonable(self.body() | {"content_address": self.content_address})
            | {
                "attribution_count": self.attribution_count,
                "claim_count": self.claim_count,
            },
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> AdapterClaimCollectionReport:
        fields = frozenset(
            {
                "version",
                "registry_snapshot",
                "adapter_metadata",
                "registry_address",
                "manifest_address",
                "context",
                "context_address",
                "adapter_ids",
                "variant_ids",
                "resolution_address",
                "attributions",
                "content_address",
                "attribution_count",
                "claim_count",
            }
        )
        raw = _strict_mapping(value, "adapter claim collection report", fields)
        _bounded_bytes(
            raw,
            "adapter claim collection report",
            _HARD_CLAIM_REPORT_BYTES,
        )
        for field_name in (
            "adapter_metadata",
            "adapter_ids",
            "variant_ids",
            "attributions",
        ):
            if type(raw[field_name]) is not list:
                raise ValidationError(f"adapter claim collection {field_name} must be an array")
        if len(raw["adapter_metadata"]) > _HARD_RESOLUTION_ADAPTERS:
            raise ValidationError("claim collection adapter metadata exceeds its hard ceiling")
        if len(raw["adapter_ids"]) > _HARD_RESOLUTION_ADAPTERS:
            raise ValidationError("claim collection exceeds its hard adapter ceiling")
        if not raw["variant_ids"] or len(raw["variant_ids"]) > _HARD_RESOLUTION_VARIANTS:
            raise ValidationError("claim collection variant count is outside its hard bounds")
        if len(raw["attributions"]) > _HARD_CLAIM_ATTRIBUTIONS:
            raise ValidationError("claim collection exceeds its hard attribution ceiling")
        for field_name in ("attribution_count", "claim_count"):
            count = raw[field_name]
            if type(count) is not int or count < 0:
                raise ValidationError(
                    f"adapter claim collection {field_name} must be a non-negative integer"
                )
        snapshot_raw = raw["registry_snapshot"]
        context_raw = raw["context"]
        if type(snapshot_raw) is not dict:
            raise ValidationError("claim collection registry snapshot must be an object")
        if type(context_raw) is not dict:
            raise ValidationError("claim collection context must be an object")
        attributions = tuple(
            AdapterClaimAttribution.from_dict(item) for item in raw["attributions"]
        )
        adapter_metadata = tuple(
            AdapterMetadata.from_dict(item) for item in raw["adapter_metadata"]
        )
        if sum(item.claim_count for item in attributions) > _HARD_CLAIMS_TOTAL:
            raise ValidationError("claim collection exceeds its hard total claim ceiling")
        result = cls(
            registry_snapshot=AdapterRegistrySnapshot.from_dict(snapshot_raw),
            adapter_metadata=adapter_metadata,
            registry_address=raw["registry_address"],
            manifest_address=raw["manifest_address"],
            context=ReferenceContext.from_dict(context_raw, persisted=True),
            context_address=raw["context_address"],
            adapter_ids=tuple(raw["adapter_ids"]),
            variant_ids=tuple(raw["variant_ids"]),
            resolution_address=raw["resolution_address"],
            attributions=attributions,
            version=raw["version"],
            content_address=raw["content_address"],
        )
        if raw["attribution_count"] != result.attribution_count:
            raise ValidationError(
                "adapter claim collection attribution_count is not derived from its items"
            )
        if raw["claim_count"] != result.claim_count:
            raise ValidationError(
                "adapter claim collection claim_count is not derived from its items"
            )
        if canonical_bytes(raw) != canonical_bytes(result.to_dict()):
            raise ValidationError(
                "adapter claim collection report is not an exact canonical representation"
            )
        return result


def _snapshot_metadata(metadata: AdapterMetadata) -> AdapterMetadata:
    return AdapterMetadata.from_dict(metadata.to_dict())


def _snapshot_limits(limits: object) -> AdapterLimits:
    if type(limits) is not AdapterLimits:
        raise ValidationError("adapter registry limits must be exact AdapterLimits")
    try:
        return AdapterLimits(**limits.to_dict())
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValidationError("adapter registry limits are invalid") from exc


class AdapterRegistry:
    """Thread-safe registry with fail-closed adapter invocation."""

    def __init__(self, limits: AdapterLimits | None = None) -> None:
        if limits is not None and type(limits) is not AdapterLimits:
            raise ValidationError("adapter registry limits must be exact AdapterLimits")
        initial_limits = AdapterLimits() if limits is None else limits
        self._limits = _snapshot_limits(initial_limits)
        self._limits_address = content_hash(self._limits.to_dict(), prefix="adapter-limits")
        self._entries: dict[str, RegistryEntry] = {}
        self._lock = RLock()

    @property
    def limits(self) -> AdapterLimits:
        return self._current_limits()

    def _current_limits(self) -> AdapterLimits:
        current = _snapshot_limits(self._limits)
        if content_hash(current.to_dict(), prefix="adapter-limits") != self._limits_address:
            raise ValidationError("adapter registry limits were mutated")
        return current

    @staticmethod
    def _read_metadata(adapter: EvidenceAdapter) -> AdapterMetadata:
        try:
            metadata = adapter.metadata
        except Exception as exc:
            raise ValidationError("adapter metadata could not be read") from exc
        if type(metadata) is not AdapterMetadata:
            raise ValidationError("adapter metadata must be exact AdapterMetadata")
        return _snapshot_metadata(metadata)

    def _assert_metadata_stable(self, entry: RegistryEntry) -> None:
        try:
            captured = _snapshot_metadata(entry.metadata)
        except (TypeError, ValueError, ValidationError) as exc:
            raise ValidationError("adapter registry metadata snapshot drift detected") from exc
        if captured.content_address != entry.metadata_address:
            raise ValidationError(f"adapter metadata drift detected: {captured.adapter_id}")
        current = self._read_metadata(entry.adapter)
        if current.content_address != entry.metadata_address or canonical_bytes(
            current.to_dict()
        ) != canonical_bytes(captured.to_dict()):
            raise ValidationError(f"adapter metadata drift detected: {captured.adapter_id}")

    def _snapshot_unlocked(self) -> AdapterRegistrySnapshot:
        entries = tuple(
            AdapterRegistrySnapshotEntry.from_metadata(self._entries[key].metadata)
            for key in sorted(self._entries)
        )
        return AdapterRegistrySnapshot(entries)

    def register(self, adapter: EvidenceAdapter) -> RegistryEntry:
        limits = self._current_limits()
        try:
            legacy_resolver = getattr(adapter, "resolve_elements", None)
            variant_resolver = getattr(adapter, "resolve_variant_elements", None)
            claim_collector = getattr(adapter, "collect_claims", None)
        except Exception as exc:
            raise ValidationError("adapter callable contract could not be read") from exc
        if not callable(legacy_resolver) and not callable(variant_resolver):
            raise ValidationError("adapter must expose a callable element resolver")
        if variant_resolver is not None and not callable(variant_resolver):
            raise ValidationError("adapter variant resolver must be callable")
        if not callable(claim_collector):
            raise ValidationError("adapter claim collector must be callable")
        metadata = self._read_metadata(adapter)
        entry = RegistryEntry(metadata, adapter, metadata.content_address)
        with self._lock:
            if metadata.adapter_id in self._entries:
                raise ValidationError(f"adapter already registered: {metadata.adapter_id}")
            if len(self._entries) >= limits.max_registered_adapters:
                raise ValidationError("adapter registry exceeds its configured ceiling")
            prospective_entries = [
                AdapterRegistrySnapshotEntry.from_metadata(self._entries[key].metadata)
                for key in sorted(self._entries)
            ]
            prospective_entries.append(AdapterRegistrySnapshotEntry.from_metadata(entry.metadata))
            prospective_snapshot = AdapterRegistrySnapshot(
                tuple(sorted(prospective_entries, key=lambda item: item.adapter_id))
            )
            _bounded_bytes(
                prospective_snapshot.to_dict(),
                "adapter registry snapshot",
                limits.max_report_bytes,
            )
            self._assert_metadata_stable(entry)
            self._current_limits()
            registered_entry = RegistryEntry(
                _snapshot_metadata(entry.metadata),
                entry.adapter,
                entry.metadata_address,
            )
            self._entries[metadata.adapter_id] = entry
        return registered_entry

    def get(self, adapter_id: str) -> EvidenceAdapter:
        self._current_limits()
        canonical_id = _token(adapter_id, "adapter_id")
        with self._lock:
            try:
                entry = self._entries[canonical_id]
            except KeyError as exc:
                raise ValidationError(f"adapter is not registered: {canonical_id}") from exc
        self._assert_metadata_stable(entry)
        self._current_limits()
        return entry.adapter

    def snapshot(self) -> AdapterRegistrySnapshot:
        self._current_limits()
        with self._lock:
            entries = tuple(self._entries[key] for key in sorted(self._entries))
            snapshot = self._snapshot_unlocked()
        for entry in entries:
            self._assert_metadata_stable(entry)
        self._current_limits()
        return snapshot

    def selected_snapshot(
        self,
        adapter_ids: tuple[str, ...],
    ) -> AdapterRegistrySnapshot:
        """Return the exact atomic snapshot that a selected invocation will bind."""

        snapshot, _entries = self.selected_entries(adapter_ids)
        return snapshot

    def selected_entries(
        self,
        adapter_ids: tuple[str, ...],
    ) -> tuple[AdapterRegistrySnapshot, tuple[RegistryEntry, ...]]:
        """Return one selected snapshot together with its exact adapter identities."""

        snapshot, entries = self._capture(adapter_ids)
        detached_entries = tuple(
            RegistryEntry(
                _snapshot_metadata(entry.metadata),
                entry.adapter,
                entry.metadata_address,
            )
            for entry in entries
        )
        return AdapterRegistrySnapshot.from_dict(snapshot.to_dict()), detached_entries

    def list_metadata(self) -> tuple[AdapterMetadata, ...]:
        self._current_limits()
        with self._lock:
            entries = tuple(self._entries[key] for key in sorted(self._entries))
        for entry in entries:
            self._assert_metadata_stable(entry)
        self._current_limits()
        return tuple(_snapshot_metadata(entry.metadata) for entry in entries)

    def discovery(
        self,
    ) -> tuple[AdapterRegistrySnapshot, tuple[AdapterMetadata, ...], AdapterLimits]:
        """Return one internally consistent full-registry discovery projection."""

        limits = self._current_limits()
        with self._lock:
            entries = tuple(self._entries[key] for key in sorted(self._entries))
            snapshot = self._snapshot_unlocked()
            metadata = tuple(_snapshot_metadata(entry.metadata) for entry in entries)
        for entry in entries:
            self._assert_metadata_stable(entry)
        self._current_limits()
        if tuple(item.adapter_id for item in metadata) != tuple(
            item.adapter_id for item in snapshot.adapters
        ):
            raise ValidationError("adapter discovery projection is internally inconsistent")
        return snapshot, metadata, limits

    def health(self) -> dict[str, Any]:
        return self.snapshot().to_dict()

    def _capture(
        self,
        adapter_ids: tuple[str, ...],
    ) -> tuple[AdapterRegistrySnapshot, tuple[RegistryEntry, ...]]:
        limits = self._current_limits()
        if type(adapter_ids) is not tuple:
            raise ValidationError("adapter_ids must be a tuple")
        canonical_ids = tuple(
            _token(item, f"adapter_ids[{index}]") for index, item in enumerate(adapter_ids)
        )
        if len(canonical_ids) != len(set(canonical_ids)):
            raise ValidationError("adapter_ids must be unique")
        if len(canonical_ids) > limits.max_selected_adapters:
            raise ValidationError("selected adapter count exceeds its configured ceiling")
        canonical_ids = tuple(sorted(canonical_ids))
        with self._lock:
            missing = tuple(item for item in canonical_ids if item not in self._entries)
            if missing:
                raise ValidationError(f"adapter is not registered: {missing[0]}")
            entries = tuple(self._entries[item] for item in canonical_ids)
            snapshot = AdapterRegistrySnapshot(
                tuple(
                    AdapterRegistrySnapshotEntry.from_metadata(entry.metadata) for entry in entries
                )
            )
        for entry in entries:
            self._assert_metadata_stable(entry)
        self._current_limits()
        return snapshot, entries

    def _validate_captured_entries(
        self,
        snapshot: AdapterRegistrySnapshot,
        entries: tuple[RegistryEntry, ...],
    ) -> tuple[AdapterRegistrySnapshot, tuple[RegistryEntry, ...]]:
        """Detach one caller-held execution capability without registry recapture.

        The executable objects in ``entries`` are the authority for this
        invocation.  Re-reading ``self._entries`` here would reintroduce the
        capture-to-use race this path exists to close.
        """

        limits = self._current_limits()
        if type(snapshot) is not AdapterRegistrySnapshot:
            raise ValidationError(
                "captured adapter snapshot must be an exact AdapterRegistrySnapshot"
            )
        try:
            canonical_snapshot = AdapterRegistrySnapshot.from_dict(snapshot.to_dict())
        except (TypeError, ValueError, OverflowError, ValidationError) as exc:
            raise ValidationError("captured adapter snapshot is invalid") from exc
        if type(entries) is not tuple:
            raise ValidationError("captured adapter entries must be an exact tuple")
        if len(entries) > limits.max_selected_adapters:
            raise ValidationError("captured adapter entry count exceeds its configured ceiling")
        if len(entries) != canonical_snapshot.count:
            raise ValidationError(
                "captured adapter entries do not exactly cover their snapshot"
            )

        pinned_entries: list[RegistryEntry] = []
        projections: list[AdapterRegistrySnapshotEntry] = []
        for entry in entries:
            if type(entry) is not RegistryEntry:
                raise ValidationError(
                    "captured adapter entries must contain exact RegistryEntry values"
                )
            try:
                metadata = _snapshot_metadata(entry.metadata)
                adapter = entry.adapter
            except (TypeError, ValueError, OverflowError, ValidationError) as exc:
                raise ValidationError("captured adapter entry is invalid") from exc
            if entry.metadata_address != metadata.content_address:
                raise ValidationError(
                    "captured adapter entry metadata address does not match its metadata"
                )
            pinned_entry = RegistryEntry(metadata, adapter, entry.metadata_address)
            self._assert_metadata_stable(pinned_entry)
            pinned_entries.append(pinned_entry)
            projections.append(AdapterRegistrySnapshotEntry.from_metadata(metadata))

        entry_ids = tuple(entry.metadata.adapter_id for entry in pinned_entries)
        if entry_ids != tuple(sorted(entry_ids)) or len(entry_ids) != len(set(entry_ids)):
            raise ValidationError("captured adapter entries must be sorted and unique")
        snapshot_ids = tuple(item.adapter_id for item in canonical_snapshot.adapters)
        if entry_ids != snapshot_ids or tuple(projections) != canonical_snapshot.adapters:
            raise ValidationError(
                "captured adapter entries do not reproduce their exact snapshot"
            )
        self._current_limits()
        return canonical_snapshot, tuple(pinned_entries)

    def _validate_manifest(self, manifest: CaseManifest) -> None:
        limits = self._current_limits()
        if type(manifest) is not CaseManifest:
            raise ValidationError("adapter resolution requires an exact CaseManifest")
        _validate_context(manifest.context)
        if type(manifest.variants) is not tuple or any(
            type(variant) is not VariantIdentity for variant in manifest.variants
        ):
            raise ValidationError("case manifest variants must be exact VariantIdentity values")
        if type(manifest.candidate_elements) is not tuple or any(
            type(element) is not CandidateElement for element in manifest.candidate_elements
        ):
            raise ValidationError(
                "case manifest candidate elements must be exact CandidateElement values"
            )
        for variant in manifest.variants:
            _validate_variant(variant)
        if len(manifest.variants) > limits.max_variants:
            raise ValidationError("case manifest variant count exceeds its configured ceiling")
        raw = manifest.to_dict()
        encoded = _bounded_bytes(raw, "case manifest", limits.max_manifest_bytes)
        try:
            reopened = CaseManifest.from_dict(raw)
        except (
            TypeError,
            ValueError,
            OverflowError,
            UnicodeError,
            RecursionError,
        ) as exc:
            raise ValidationError("case manifest is not canonical") from exc
        if encoded != canonical_bytes(reopened.to_dict()):
            raise ValidationError("case manifest is not an exact canonical representation")
        if any(
            variant.genome_build != manifest.context.genome_build for variant in manifest.variants
        ):
            raise ValidationError("case variant escaped the manifest genome build")
        self._current_limits()

    def _invoke(
        self,
        entry: RegistryEntry,
        variant: VariantIdentity,
        context: ReferenceContext,
        *,
        remaining_elements: int,
        after_callback: Callable[[], None] | None,
    ) -> tuple[CandidateElement, ...]:
        limits = self._current_limits()
        if type(remaining_elements) is not int or not 0 <= remaining_elements <= (
            limits.max_elements_total
        ):
            raise ValidationError("adapter resolution remaining element allowance is invalid")
        metadata = entry.metadata
        canonical_variant = _validate_variant(variant)
        canonical_context = _validate_context(context)
        invocation_variant_bytes = canonical_bytes(canonical_variant.to_dict())
        invocation_context_bytes = canonical_bytes(canonical_context.to_dict())
        _require_supported_context(metadata, canonical_context)
        self._assert_metadata_stable(entry)
        try:
            variant_resolver = getattr(entry.adapter, "resolve_variant_elements", None)
            if variant_resolver is None:
                self._assert_metadata_stable(entry)
                resolver = entry.adapter.resolve_elements
                if not callable(resolver):
                    raise TypeError("resolve_elements is not callable")
                self._assert_metadata_stable(entry)
                result = resolver(
                    canonical_variant.variant_id,
                    canonical_context,
                )
            else:
                if not callable(variant_resolver):
                    raise TypeError("resolve_variant_elements is not callable")
                self._assert_metadata_stable(entry)
                result = variant_resolver(
                    canonical_variant,
                    canonical_context,
                )
        except Exception as exc:
            self._assert_metadata_stable(entry)
            raise ValidationError(f"adapter resolution failed: {metadata.adapter_id}") from exc
        if after_callback is not None:
            after_callback()
        self._assert_metadata_stable(entry)
        self._current_limits()
        try:
            current_variant_bytes = canonical_bytes(canonical_variant.to_dict())
            current_context_bytes = canonical_bytes(canonical_context.to_dict())
        except (TypeError, ValueError, OverflowError, UnicodeError, RecursionError) as exc:
            raise ValidationError(
                f"adapter mutated its resolution invocation inputs: {metadata.adapter_id}"
            ) from exc
        if (
            current_variant_bytes != invocation_variant_bytes
            or current_context_bytes != invocation_context_bytes
        ):
            raise ValidationError(
                f"adapter mutated its resolution invocation inputs: {metadata.adapter_id}"
            )
        if type(result) is not tuple:
            raise ValidationError(
                f"adapter resolution must return an exact tuple: {metadata.adapter_id}"
            )
        if len(result) > limits.max_elements_per_variant:
            raise ValidationError(
                f"adapter resolution exceeds its per-variant ceiling: {metadata.adapter_id}"
            )
        if len(result) > remaining_elements:
            raise ValidationError("adapter resolution exceeds its total element ceiling")
        validated: list[CandidateElement] = []
        identities: set[str] = set()
        for element in result:
            item = _validate_candidate_element(
                element,
                canonical_context,
                limits.max_item_bytes,
            )
            if item.element_id in identities:
                raise ValidationError(
                    f"adapter returned duplicate element identity: {item.element_id}"
                )
            identities.add(item.element_id)
            if not metadata.source_ids:
                raise ValidationError(f"adapter does not declare source IDs: {metadata.adapter_id}")
            if item.source_id not in metadata.source_ids:
                raise ValidationError(
                    f"adapter element escaped declared sources: {metadata.adapter_id}"
                )
            validated.append(item)
        return tuple(sorted(validated, key=lambda item: item.element_id))

    def _invoke_claim_collector(
        self,
        entry: RegistryEntry,
        resolution_item: AdapterResolutionItem,
        context: ReferenceContext,
        *,
        remaining_claims: int,
        remaining_bytes: int,
        remaining_claims_by_edge: Mapping[str, int] | None,
        after_callback: Callable[[], None] | None,
    ) -> tuple[tuple[EvidenceClaim, ...], int, dict[str, int]]:
        """Invoke one captured adapter and detach its bounded exact claim tuple."""

        limits = self._current_limits()
        metadata = entry.metadata
        _token(resolution_item.variant_id, "claim collection variant_id")
        _token(resolution_item.element.element_id, "claim collection element_id")
        canonical_context = _validate_context(context)
        _require_supported_context(metadata, canonical_context)
        invocation_context = ReferenceContext.from_dict(
            canonical_context.to_dict(),
            persisted=True,
        )
        invocation_context_bytes = canonical_bytes(invocation_context.to_dict())
        self._assert_metadata_stable(entry)
        try:
            collector = entry.adapter.collect_claims
            if not callable(collector):
                raise TypeError("collect_claims is not callable")
            result = collector(
                resolution_item.variant_id,
                resolution_item.element.element_id,
                invocation_context,
            )
        except Exception as exc:
            self._assert_metadata_stable(entry)
            raise ValidationError(
                f"adapter claim collection failed: {metadata.adapter_id}"
            ) from exc
        if after_callback is not None:
            after_callback()
        self._assert_metadata_stable(entry)
        self._current_limits()
        try:
            current_context_bytes = canonical_bytes(invocation_context.to_dict())
        except (TypeError, ValueError, OverflowError, UnicodeError, RecursionError) as exc:
            raise ValidationError(
                f"adapter mutated its claim invocation context: {metadata.adapter_id}"
            ) from exc
        if current_context_bytes != invocation_context_bytes:
            raise ValidationError(
                f"adapter mutated its claim invocation context: {metadata.adapter_id}"
            )
        if type(result) is not tuple:
            raise ValidationError(
                f"adapter claim collection must return an exact tuple: {metadata.adapter_id}"
            )
        if len(result) > limits.max_claims_per_element:
            raise ValidationError(
                f"adapter claim collection exceeds its per-element ceiling: {metadata.adapter_id}"
            )
        if len(result) > remaining_claims:
            raise ValidationError("adapter claim collection exceeds its total claim ceiling")
        validated: list[EvidenceClaim] = []
        identities: set[str] = set()
        used_bytes = 0
        used_by_edge: dict[str, int] = {}
        owned_edge_ids = _resolution_item_edge_ids(
            resolution_item.variant_id,
            resolution_item.element,
        )
        for claim in result:
            canonical_claim, claim_bytes = _validate_evidence_claim(
                claim,
                canonical_context,
                limits.max_item_bytes,
            )
            if canonical_claim.evidence_id in identities:
                raise ValidationError(
                    "adapter claim collection returned a duplicate evidence ID: "
                    f"{canonical_claim.evidence_id}"
                )
            identities.add(canonical_claim.evidence_id)
            if canonical_claim.source_id not in metadata.source_ids:
                raise ValidationError(
                    f"adapter claim escaped declared sources: {metadata.adapter_id}"
                )
            if canonical_claim.channel not in metadata.channels:
                raise ValidationError(
                    f"adapter claim escaped declared channels: {metadata.adapter_id}"
                )
            if canonical_claim.produced_by != metadata.adapter_id:
                raise ValidationError(
                    f"adapter claim producer does not match its attribution: {metadata.adapter_id}"
                )
            edge_id = canonical_claim.edge_id
            if edge_id not in owned_edge_ids:
                raise ValidationError(
                    "adapter claim edge does not belong to its attributed resolution item"
                )
            if remaining_claims_by_edge is not None:
                edge_count = used_by_edge.get(edge_id, 0) + 1
                if edge_count > remaining_claims_by_edge.get(edge_id, 0):
                    raise ValidationError(
                        "adapter claim collection exceeds its per-edge claim ceiling"
                    )
                used_by_edge[edge_id] = edge_count
            if claim_bytes > remaining_bytes - used_bytes:
                raise ValidationError(
                    "adapter claim collection exceeds its configured report byte ceiling"
                )
            used_bytes += claim_bytes
            validated.append(canonical_claim)
        self._assert_metadata_stable(entry)
        self._current_limits()
        return tuple(validated), used_bytes, used_by_edge

    def _validate_claim_resolution(
        self,
        manifest: CaseManifest,
        resolution: object,
    ) -> AdapterResolutionReport:
        """Detach and bind an exact resolution report to the supplied manifest."""

        limits = self._current_limits()
        if type(resolution) is not AdapterResolutionReport:
            raise ValidationError(
                "adapter claim collection requires an exact AdapterResolutionReport"
            )
        canonical = AdapterResolutionReport.from_dict(resolution.to_dict())
        canonical.validate_manifest(manifest)
        if canonical.manifest_address != manifest.content_address:
            raise ValidationError(
                "adapter claim resolution does not belong to the supplied manifest"
            )
        context_address = content_hash(
            manifest.context.to_dict(),
            prefix="adapter-context",
        )
        if canonical.context_address != context_address:
            raise ValidationError(
                "adapter claim resolution context does not match the supplied manifest"
            )
        variants = {variant.variant_id: variant for variant in manifest.variants}
        if canonical.variant_ids != tuple(sorted(variants)):
            raise ValidationError(
                "adapter claim resolution variants do not match the supplied manifest"
            )
        if len(canonical.items) > limits.max_elements_total:
            raise ValidationError(
                "adapter claim resolution exceeds the configured total element ceiling"
            )
        invocation_counts: dict[tuple[str, str], int] = {}
        for item in canonical.items:
            variant = variants[item.variant_id]
            expected_variant_address = content_hash(
                variant.to_dict(),
                prefix="adapter-variant",
            )
            if item.variant_address != expected_variant_address:
                raise ValidationError(
                    "adapter claim resolution variant address does not match the manifest"
                )
            if item.element.context.key != manifest.context.key:
                raise ValidationError(
                    "adapter claim resolution element escaped the manifest context"
                )
            _validate_candidate_element(
                item.element,
                manifest.context,
                limits.max_item_bytes,
            )
            invocation_key = item.adapter_id, item.variant_id
            invocation_count = invocation_counts.get(invocation_key, 0) + 1
            if invocation_count > limits.max_elements_per_variant:
                raise ValidationError(
                    "adapter claim resolution exceeds the configured per-variant element ceiling"
                )
            invocation_counts[invocation_key] = invocation_count
        _bounded_bytes(
            canonical.to_dict(),
            "adapter claim resolution report",
            limits.max_report_bytes,
        )
        self._current_limits()
        return canonical

    def resolve_manifest(
        self,
        manifest: CaseManifest,
        adapter_ids: tuple[str, ...],
        *,
        after_callback: Callable[[], None] | None = None,
    ) -> AdapterResolutionReport:
        """Resolve a manifest against one atomic registry snapshot."""

        limits = self._current_limits()
        canonical_after_callback = _optional_after_callback(after_callback)
        self._validate_manifest(manifest)
        canonical_manifest = CaseManifest.from_dict(manifest.to_dict())
        snapshot, entries = self._capture(adapter_ids)
        return self._resolve_manifest_entries_impl(
            canonical_manifest,
            snapshot,
            entries,
            limits=limits,
            after_callback=canonical_after_callback,
        )

    def resolve_manifest_entries(
        self,
        manifest: CaseManifest,
        snapshot: AdapterRegistrySnapshot,
        entries: tuple[RegistryEntry, ...],
        *,
        after_callback: Callable[[], None] | None = None,
    ) -> AdapterResolutionReport:
        """Resolve with caller-captured executable identities, without recapture."""

        limits = self._current_limits()
        canonical_after_callback = _optional_after_callback(after_callback)
        self._validate_manifest(manifest)
        canonical_manifest = CaseManifest.from_dict(manifest.to_dict())
        canonical_snapshot, pinned_entries = self._validate_captured_entries(
            snapshot,
            entries,
        )
        return self._resolve_manifest_entries_impl(
            canonical_manifest,
            canonical_snapshot,
            pinned_entries,
            limits=limits,
            after_callback=canonical_after_callback,
        )

    def _resolve_manifest_entries_impl(
        self,
        canonical_manifest: CaseManifest,
        snapshot: AdapterRegistrySnapshot,
        entries: tuple[RegistryEntry, ...],
        *,
        limits: AdapterLimits,
        after_callback: Callable[[], None] | None,
    ) -> AdapterResolutionReport:
        """Execute one already validated and pinned resolution capability."""

        variants = tuple(sorted(canonical_manifest.variants, key=lambda item: item.variant_id))
        selected_adapter_ids = tuple(entry.metadata.adapter_id for entry in entries)
        selected_variant_ids = tuple(variant.variant_id for variant in variants)
        context_address = content_hash(
            canonical_manifest.context.to_dict(),
            prefix="adapter-context",
        )
        empty_report = AdapterResolutionReport(
            registry_address=snapshot.content_address,
            manifest_address=canonical_manifest.content_address,
            context_address=context_address,
            adapter_ids=selected_adapter_ids,
            variant_ids=selected_variant_ids,
            items=(),
        )
        report_size = len(
            _bounded_bytes(
                empty_report.to_dict(),
                "adapter resolution report",
                limits.max_report_bytes,
            )
        )
        items: list[AdapterResolutionItem] = []
        canonical_elements: dict[str, bytes] = {}
        for entry in entries:
            for variant in variants:
                remaining_elements = limits.max_elements_total - len(items)
                if remaining_elements <= 0:
                    raise ValidationError("adapter resolution exceeds its total element ceiling")
                variant_address = content_hash(variant.to_dict(), prefix="adapter-variant")
                for element in self._invoke(
                    entry,
                    variant,
                    canonical_manifest.context,
                    remaining_elements=remaining_elements,
                    after_callback=after_callback,
                ):
                    encoded = canonical_bytes(element.to_dict())
                    previous = canonical_elements.get(element.element_id)
                    if previous is not None and previous != encoded:
                        raise ValidationError(
                            "adapter resolution has conflicting element identity: "
                            f"{element.element_id}"
                        )
                    resolution_item = AdapterResolutionItem(
                        adapter_id=entry.metadata.adapter_id,
                        metadata_address=entry.metadata_address,
                        variant_id=variant.variant_id,
                        variant_address=variant_address,
                        element=element,
                    )
                    attribution_count = len(items)
                    element_count = len(canonical_elements)
                    prospective_size = (
                        report_size
                        + len(canonical_bytes(resolution_item.to_dict()))
                        + (1 if attribution_count else 0)
                        + len(str(attribution_count + 1))
                        - len(str(attribution_count))
                    )
                    if previous is None:
                        prospective_size += len(str(element_count + 1)) - len(str(element_count))
                    if prospective_size > limits.max_report_bytes:
                        raise ValidationError(
                            "adapter resolution exceeds its configured report byte ceiling"
                        )
                    report_size = prospective_size
                    canonical_elements.setdefault(element.element_id, encoded)
                    items.append(resolution_item)
        report = AdapterResolutionReport(
            registry_address=snapshot.content_address,
            manifest_address=canonical_manifest.content_address,
            context_address=context_address,
            adapter_ids=selected_adapter_ids,
            variant_ids=selected_variant_ids,
            items=tuple(sorted(items, key=lambda item: item.identity)),
        )
        _bounded_bytes(
            report.to_dict(),
            "adapter resolution report",
            limits.max_report_bytes,
        )
        for entry in entries:
            self._assert_metadata_stable(entry)
        self._current_limits()
        return report

    def _prepare_claim_collection(
        self,
        manifest: CaseManifest,
        resolution: AdapterResolutionReport,
        *,
        max_claims: int | None = None,
        max_claims_by_edge: Mapping[str, int] | None = None,
        after_callback: Callable[[], None] | None = None,
    ) -> tuple[
        AdapterLimits,
        Callable[[], None] | None,
        dict[str, int] | None,
        int,
        CaseManifest,
        AdapterResolutionReport,
    ]:
        """Validate and detach the registry-independent claim inputs."""

        limits = self._current_limits()
        canonical_after_callback = _optional_after_callback(after_callback)
        edge_claim_limits = _snapshot_claim_limits_by_edge(max_claims_by_edge)
        if max_claims is not None and (
            type(max_claims) is not int or not 0 <= max_claims <= _HARD_CLAIMS_TOTAL
        ):
            raise ValidationError(
                f"adapter max_claims must be an integer between 0 and {_HARD_CLAIMS_TOTAL}"
            )
        claim_ceiling = (
            limits.max_claims_total
            if max_claims is None
            else min(limits.max_claims_total, max_claims)
        )
        self._validate_manifest(manifest)
        canonical_manifest = CaseManifest.from_dict(manifest.to_dict())
        canonical_resolution = self._validate_claim_resolution(
            canonical_manifest,
            resolution,
        )
        return (
            limits,
            canonical_after_callback,
            edge_claim_limits,
            claim_ceiling,
            canonical_manifest,
            canonical_resolution,
        )

    def collect_claims(
        self,
        manifest: CaseManifest,
        resolution: AdapterResolutionReport,
        *,
        max_claims: int | None = None,
        max_claims_by_edge: Mapping[str, int] | None = None,
        after_callback: Callable[[], None] | None = None,
    ) -> AdapterClaimCollectionReport:
        """Collect claims against one snapshot captured by this call."""

        (
            limits,
            canonical_after_callback,
            edge_claim_limits,
            claim_ceiling,
            canonical_manifest,
            canonical_resolution,
        ) = self._prepare_claim_collection(
            manifest,
            resolution,
            max_claims=max_claims,
            max_claims_by_edge=max_claims_by_edge,
            after_callback=after_callback,
        )
        snapshot, entries = self._capture(canonical_resolution.adapter_ids)
        return self._collect_claims_entries_impl(
            canonical_manifest,
            canonical_resolution,
            snapshot,
            entries,
            limits=limits,
            after_callback=canonical_after_callback,
            edge_claim_limits=edge_claim_limits,
            claim_ceiling=claim_ceiling,
        )

    def collect_claims_entries(
        self,
        manifest: CaseManifest,
        resolution: AdapterResolutionReport,
        snapshot: AdapterRegistrySnapshot,
        entries: tuple[RegistryEntry, ...],
        *,
        max_claims: int | None = None,
        max_claims_by_edge: Mapping[str, int] | None = None,
        after_callback: Callable[[], None] | None = None,
    ) -> AdapterClaimCollectionReport:
        """Collect claims with caller-captured identities, without recapture."""

        (
            limits,
            canonical_after_callback,
            edge_claim_limits,
            claim_ceiling,
            canonical_manifest,
            canonical_resolution,
        ) = self._prepare_claim_collection(
            manifest,
            resolution,
            max_claims=max_claims,
            max_claims_by_edge=max_claims_by_edge,
            after_callback=after_callback,
        )
        canonical_snapshot, pinned_entries = self._validate_captured_entries(
            snapshot,
            entries,
        )
        return self._collect_claims_entries_impl(
            canonical_manifest,
            canonical_resolution,
            canonical_snapshot,
            pinned_entries,
            limits=limits,
            after_callback=canonical_after_callback,
            edge_claim_limits=edge_claim_limits,
            claim_ceiling=claim_ceiling,
        )

    def _collect_claims_entries_impl(
        self,
        canonical_manifest: CaseManifest,
        canonical_resolution: AdapterResolutionReport,
        snapshot: AdapterRegistrySnapshot,
        entries: tuple[RegistryEntry, ...],
        *,
        limits: AdapterLimits,
        after_callback: Callable[[], None] | None,
        edge_claim_limits: dict[str, int] | None,
        claim_ceiling: int,
    ) -> AdapterClaimCollectionReport:
        """Execute one already validated and pinned claim capability."""

        if snapshot.content_address != canonical_resolution.registry_address:
            raise ValidationError("adapter claim resolution registry snapshot is no longer current")
        entries_by_id = {entry.metadata.adapter_id: entry for entry in entries}
        for item in canonical_resolution.items:
            entry = entries_by_id[item.adapter_id]
            if item.metadata_address != entry.metadata_address:
                raise ValidationError(
                    "adapter claim resolution metadata does not match the captured registry"
                )
            if item.element.source_id not in entry.metadata.source_ids:
                raise ValidationError(
                    "adapter claim resolution element escaped declared adapter sources"
                )

        selected_metadata = tuple(_snapshot_metadata(entry.metadata) for entry in entries)
        empty_attributions = tuple(
            AdapterClaimAttribution(
                adapter_id=item.adapter_id,
                metadata_address=item.metadata_address,
                variant_id=item.variant_id,
                variant_address=item.variant_address,
                element_id=item.element.element_id,
                element_address=item.element_address,
                resolution_item_address=item.content_address,
                claims=(),
            )
            for item in canonical_resolution.items
        )
        minimum_report = AdapterClaimCollectionReport(
            registry_snapshot=snapshot,
            adapter_metadata=selected_metadata,
            manifest_address=canonical_manifest.content_address,
            context=canonical_manifest.context,
            adapter_ids=canonical_resolution.adapter_ids,
            variant_ids=canonical_resolution.variant_ids,
            resolution_address=canonical_resolution.content_address,
            attributions=empty_attributions,
        )
        minimum_report.validate_resolution(canonical_resolution)
        report_size = len(
            _bounded_bytes(
                minimum_report.to_dict(),
                "adapter claim collection report",
                limits.max_report_bytes,
            )
        )
        empty_attribution_sizes = tuple(
            len(canonical_bytes(attribution.to_dict())) for attribution in empty_attributions
        )

        attributions: list[AdapterClaimAttribution] = []
        evidence_ids: set[str] = set()
        claim_count = 0
        claim_bytes = 0
        remaining_edge_claims = None if edge_claim_limits is None else dict(edge_claim_limits)
        for attribution_index, resolution_item in enumerate(canonical_resolution.items):
            if claim_count >= claim_ceiling:
                raise ValidationError("adapter claim collection exceeds its total claim ceiling")
            if remaining_edge_claims is not None:
                possible_edges = _resolution_item_edge_ids(
                    resolution_item.variant_id,
                    resolution_item.element,
                )
                if any(remaining_edge_claims.get(edge_id, 0) <= 0 for edge_id in possible_edges):
                    raise ValidationError(
                        "adapter claim collection exceeds its per-edge claim ceiling"
                    )
            entry = entries_by_id[resolution_item.adapter_id]
            claims, encoded_bytes, used_by_edge = self._invoke_claim_collector(
                entry,
                resolution_item,
                canonical_manifest.context,
                remaining_claims=claim_ceiling - claim_count,
                remaining_bytes=limits.max_report_bytes - claim_bytes,
                remaining_claims_by_edge=remaining_edge_claims,
                after_callback=after_callback,
            )
            duplicate_ids = tuple(
                claim.evidence_id for claim in claims if claim.evidence_id in evidence_ids
            )
            if duplicate_ids:
                raise ValidationError(
                    "adapter claim collection evidence IDs must be globally unique: "
                    f"{duplicate_ids[0]}"
                )
            attribution = AdapterClaimAttribution(
                adapter_id=resolution_item.adapter_id,
                metadata_address=resolution_item.metadata_address,
                variant_id=resolution_item.variant_id,
                variant_address=resolution_item.variant_address,
                element_id=resolution_item.element.element_id,
                element_address=resolution_item.element_address,
                resolution_item_address=resolution_item.content_address,
                claims=claims,
            )
            encoded_attribution = _bounded_bytes(
                attribution.to_dict(),
                "adapter claim attribution",
                limits.max_report_bytes,
            )
            prospective_claim_count = claim_count + len(claims)
            prospective_size = (
                report_size
                + len(encoded_attribution)
                - empty_attribution_sizes[attribution_index]
                + len(str(prospective_claim_count))
                - len(str(claim_count))
            )
            if prospective_size > limits.max_report_bytes:
                raise ValidationError(
                    "adapter claim collection exceeds its configured report byte ceiling"
                )
            report_size = prospective_size
            evidence_ids.update(claim.evidence_id for claim in claims)
            claim_count = prospective_claim_count
            claim_bytes += encoded_bytes
            if remaining_edge_claims is not None:
                for edge_id, used in used_by_edge.items():
                    remaining_edge_claims[edge_id] -= used
            attributions.append(attribution)
        for entry in entries:
            self._assert_metadata_stable(entry)
        self._current_limits()
        report = AdapterClaimCollectionReport(
            registry_snapshot=snapshot,
            adapter_metadata=selected_metadata,
            manifest_address=canonical_manifest.content_address,
            context=canonical_manifest.context,
            adapter_ids=canonical_resolution.adapter_ids,
            variant_ids=canonical_resolution.variant_ids,
            resolution_address=canonical_resolution.content_address,
            attributions=tuple(attributions),
        )
        report.validate_claim_ownership(canonical_resolution)
        _bounded_bytes(
            report.to_dict(),
            "adapter claim collection report",
            limits.max_report_bytes,
        )
        for entry in entries:
            self._assert_metadata_stable(entry)
        self._current_limits()
        return report

    def resolve_for_manifest(
        self, manifest: CaseManifest, adapter_ids: tuple[str, ...]
    ) -> tuple[CandidateElement, ...]:
        """Return the historical tuple projection of :meth:`resolve_manifest`."""

        return self.resolve_manifest(manifest, adapter_ids).elements


__all__ = [
    "ADAPTER_CLAIM_COLLECTION_VERSION",
    "ADAPTER_HARD_MAX_CLAIMS_PER_ELEMENT",
    "ADAPTER_HARD_MAX_CLAIMS_TOTAL",
    "ADAPTER_HARD_MAX_ELEMENTS_PER_VARIANT",
    "ADAPTER_HARD_MAX_ELEMENTS_TOTAL",
    "ADAPTER_HARD_MAX_ITEM_BYTES",
    "ADAPTER_HARD_MAX_MANIFEST_BYTES",
    "ADAPTER_HARD_MAX_REGISTERED",
    "ADAPTER_HARD_MAX_REPORT_BYTES",
    "ADAPTER_HARD_MAX_SELECTED",
    "ADAPTER_HARD_MAX_VARIANTS",
    "ADAPTER_METADATA_VERSION",
    "ADAPTER_REGISTRY_VERSION",
    "ADAPTER_RESOLUTION_VERSION",
    "AdapterClaimAttribution",
    "AdapterClaimCollectionReport",
    "AdapterLimits",
    "AdapterMetadata",
    "AdapterRegistry",
    "AdapterRegistrySnapshot",
    "AdapterRegistrySnapshotEntry",
    "AdapterResolutionItem",
    "AdapterResolutionReport",
    "EvidenceAdapter",
    "RegistryEntry",
    "StaticElementAdapter",
    "VariantAwareEvidenceAdapter",
]
