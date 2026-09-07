"""Bounded, content-addressed adapter contracts.

Adapters are an untrusted extension boundary. Registration snapshots metadata,
resolution binds every returned element to the adapter and variant that produced
it, and caller-configurable limits may only tighten hard process ceilings.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from pathlib import PurePosixPath
from threading import RLock
from typing import Any, Protocol
from urllib.parse import urlsplit

from .errors import ValidationError
from .models import (
    CandidateElement,
    CaseManifest,
    EvidenceClaim,
    ReferenceContext,
    VariantIdentity,
)
from .serialization import canonical_bytes, content_hash, jsonable

ADAPTER_METADATA_VERSION = "adapter-metadata-v1"
ADAPTER_REGISTRY_VERSION = "adapter-registry-v1"
ADAPTER_RESOLUTION_VERSION = "adapter-resolution-v1"

ADAPTER_HARD_MAX_REGISTERED = 256
ADAPTER_HARD_MAX_SELECTED = 64
ADAPTER_HARD_MAX_VARIANTS = 10_000
ADAPTER_HARD_MAX_ELEMENTS_PER_VARIANT = 10_000
ADAPTER_HARD_MAX_ELEMENTS_TOTAL = 100_000
ADAPTER_HARD_MAX_CLAIMS_PER_ELEMENT = 10_000
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
        return jsonable(self.body() | {"content_address": self.content_address})

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
    return context


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
    return variant


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
    return element


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
        return jsonable(self)

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
        return jsonable(self.body() | {"content_address": self.content_address})

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
        return jsonable(self.body() | {"content_address": self.content_address})

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
        return jsonable(self.body() | {"content_address": self.content_address}) | {
            "element_count": self.element_count,
            "attribution_count": self.attribution_count,
        }

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
        current = self._read_metadata(entry.adapter)
        if current.content_address != entry.metadata_address:
            raise ValidationError(f"adapter metadata drift detected: {entry.metadata.adapter_id}")

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
            self._entries[metadata.adapter_id] = entry
        try:
            self._assert_metadata_stable(entry)
            self._current_limits()
        except Exception:
            with self._lock:
                if self._entries.get(metadata.adapter_id) is entry:
                    del self._entries[metadata.adapter_id]
            raise
        return entry

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

    def list_metadata(self) -> tuple[AdapterMetadata, ...]:
        self._current_limits()
        with self._lock:
            entries = tuple(self._entries[key] for key in sorted(self._entries))
        for entry in entries:
            self._assert_metadata_stable(entry)
        self._current_limits()
        return tuple(_snapshot_metadata(entry.metadata) for entry in entries)

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
            snapshot = self._snapshot_unlocked()
        for entry in entries:
            self._assert_metadata_stable(entry)
        self._current_limits()
        return snapshot, entries

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
    ) -> tuple[CandidateElement, ...]:
        limits = self._current_limits()
        metadata = entry.metadata
        canonical_variant = _validate_variant(variant)
        canonical_context = _validate_context(context)
        _require_supported_context(metadata, canonical_context)
        try:
            variant_resolver = getattr(entry.adapter, "resolve_variant_elements", None)
            if variant_resolver is None:
                resolver = entry.adapter.resolve_elements
                if not callable(resolver):
                    raise TypeError("resolve_elements is not callable")
                result = resolver(
                    canonical_variant.variant_id,
                    canonical_context,
                )
            else:
                if not callable(variant_resolver):
                    raise TypeError("resolve_variant_elements is not callable")
                result = variant_resolver(
                    canonical_variant,
                    canonical_context,
                )
        except Exception as exc:
            self._assert_metadata_stable(entry)
            raise ValidationError(f"adapter resolution failed: {metadata.adapter_id}") from exc
        self._assert_metadata_stable(entry)
        self._current_limits()
        if type(result) is not tuple:
            raise ValidationError(
                f"adapter resolution must return an exact tuple: {metadata.adapter_id}"
            )
        if len(result) > limits.max_elements_per_variant:
            raise ValidationError(
                f"adapter resolution exceeds its per-variant ceiling: {metadata.adapter_id}"
            )
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

    def resolve_manifest(
        self,
        manifest: CaseManifest,
        adapter_ids: tuple[str, ...],
    ) -> AdapterResolutionReport:
        """Resolve a manifest against one atomic registry snapshot."""

        limits = self._current_limits()
        self._validate_manifest(manifest)
        snapshot, entries = self._capture(adapter_ids)
        variants = tuple(sorted(manifest.variants, key=lambda item: item.variant_id))
        items: list[AdapterResolutionItem] = []
        canonical_elements: dict[str, bytes] = {}
        for entry in entries:
            for variant in variants:
                variant_address = content_hash(variant.to_dict(), prefix="adapter-variant")
                for element in self._invoke(entry, variant, manifest.context):
                    encoded = canonical_bytes(element.to_dict())
                    previous = canonical_elements.setdefault(element.element_id, encoded)
                    if previous != encoded:
                        raise ValidationError(
                            "adapter resolution has conflicting element identity: "
                            f"{element.element_id}"
                        )
                    items.append(
                        AdapterResolutionItem(
                            adapter_id=entry.metadata.adapter_id,
                            metadata_address=entry.metadata_address,
                            variant_id=variant.variant_id,
                            variant_address=variant_address,
                            element=element,
                        )
                    )
                    if len(items) > limits.max_elements_total:
                        raise ValidationError(
                            "adapter resolution exceeds its total element ceiling"
                        )
        report = AdapterResolutionReport(
            registry_address=snapshot.content_address,
            manifest_address=manifest.content_address,
            context_address=content_hash(manifest.context.to_dict(), prefix="adapter-context"),
            adapter_ids=tuple(entry.metadata.adapter_id for entry in entries),
            variant_ids=tuple(variant.variant_id for variant in variants),
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

    def resolve_for_manifest(
        self, manifest: CaseManifest, adapter_ids: tuple[str, ...]
    ) -> tuple[CandidateElement, ...]:
        """Return the historical tuple projection of :meth:`resolve_manifest`."""

        return self.resolve_manifest(manifest, adapter_ids).elements


__all__ = [
    "ADAPTER_HARD_MAX_CLAIMS_PER_ELEMENT",
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
