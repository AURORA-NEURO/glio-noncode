"""Bounded adapter contracts for public and institution-owned data sources."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol

from .errors import ValidationError
from .models import CandidateElement, CaseManifest, EvidenceClaim, ReferenceContext
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class AdapterMetadata:
    """Metadata required before an adapter can contribute evidence."""

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

    def __post_init__(self) -> None:
        for name in ("adapter_id", "display_name", "version", "license", "data_access"):
            if not getattr(self, name).strip():
                raise ValidationError(f"adapter metadata field is empty: {name}")
        if not self.channels:
            raise ValidationError("adapter must declare at least one channel")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class EvidenceAdapter(Protocol):
    """Protocol for a source adapter that never mutates canonical state."""

    metadata: AdapterMetadata

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


@dataclass(frozen=True, slots=True)
class StaticElementAdapter:
    """Fixture-friendly adapter backed by an immutable element collection."""

    metadata: AdapterMetadata
    elements: tuple[CandidateElement, ...] = ()

    def resolve_elements(self, variant_id: str, context: ReferenceContext) -> tuple[CandidateElement, ...]:
        return tuple(element for element in self.elements if element.context.genome_build == context.genome_build)

    def collect_claims(self, variant_id: str, element_id: str, context: ReferenceContext) -> tuple[EvidenceClaim, ...]:
        return ()


@dataclass(frozen=True, slots=True)
class RegistryEntry:
    """Registered adapter and its integrity address."""

    metadata: AdapterMetadata
    adapter: EvidenceAdapter
    metadata_address: str


class AdapterRegistry:
    """Explicit registry that rejects duplicate or incompatible adapters."""

    def __init__(self) -> None:
        self._entries: dict[str, RegistryEntry] = {}

    def register(self, adapter: EvidenceAdapter) -> RegistryEntry:
        adapter_id = adapter.metadata.adapter_id
        if adapter_id in self._entries:
            raise ValidationError(f"adapter already registered: {adapter_id}")
        address = content_hash(adapter.metadata.to_dict())
        entry = RegistryEntry(adapter.metadata, adapter, address)
        self._entries[adapter_id] = entry
        return entry

    def get(self, adapter_id: str) -> EvidenceAdapter:
        try:
            return self._entries[adapter_id].adapter
        except KeyError as exc:
            raise ValidationError(f"adapter is not registered: {adapter_id}") from exc

    def list_metadata(self) -> tuple[AdapterMetadata, ...]:
        return tuple(entry.metadata for entry in self._entries.values())

    def health(self) -> dict[str, Any]:
        return {
            "count": len(self._entries),
            "adapters": [
                {
                    "adapter_id": entry.metadata.adapter_id,
                    "version": entry.metadata.version,
                    "validation_status": entry.metadata.validation_status,
                    "metadata_address": entry.metadata_address,
                }
                for entry in self._entries.values()
            ],
        }

    def resolve_for_manifest(self, manifest: CaseManifest, adapter_ids: tuple[str, ...]) -> tuple[CandidateElement, ...]:
        elements: list[CandidateElement] = []
        for adapter_id in adapter_ids:
            adapter = self.get(adapter_id)
            for variant in manifest.variants:
                elements.extend(adapter.resolve_elements(variant.variant_id, manifest.context))
        deduplicated = {element.element_id: element for element in elements}
        return tuple(deduplicated[key] for key in sorted(deduplicated))
