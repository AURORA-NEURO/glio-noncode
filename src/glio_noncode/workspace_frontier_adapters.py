"""Input adapters and receipts for workspace frontier projections."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty
from .workspace_frontier_public_data import WorkspaceFrontierOperation


class WorkspaceFrontierAdapterKind(StrEnum):
    CASE_MANIFEST = "case_manifest"
    COHORT_RECORDS = "cohort_records"
    VARIANT_IDENTITY = "variant_identity"
    INTERVAL_TRACK = "interval_track"


@dataclass(frozen=True, slots=True)
class WorkspaceFrontierInputAdapter:
    adapter_id: str
    kind: WorkspaceFrontierAdapterKind
    operation: WorkspaceFrontierOperation
    accepted_formats: tuple[str, ...]
    required_fields: tuple[str, ...]
    normalization_rules: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.adapter_id, "adapter_id")
        if not self.accepted_formats or not self.required_fields:
            raise ValueError("workspace adapter requires formats and fields")

    def inspect(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        present = tuple(sorted(str(key) for key in payload))
        missing = tuple(field for field in self.required_fields if field not in payload)
        return {"adapter_id": self.adapter_id, "kind": self.kind.value, "operation": self.operation.value, "present_fields": present, "missing_fields": missing, "accepted": not missing, "normalization_rules": self.normalization_rules}

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkspaceFrontierAdapterReceipt:
    adapter_id: str
    input_address: str
    accepted: bool
    missing_fields: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkspaceFrontierAdapterRegistry:
    adapters: tuple[WorkspaceFrontierInputAdapter, ...]
    content_address: str

    def by_operation(self, operation: WorkspaceFrontierOperation) -> WorkspaceFrontierInputAdapter:
        return next(item for item in self.adapters if item.operation is operation)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_workspace_frontier_adapters() -> WorkspaceFrontierAdapterRegistry:
    adapters = (
        WorkspaceFrontierInputAdapter("adapter-case-manifest", WorkspaceFrontierAdapterKind.CASE_MANIFEST, WorkspaceFrontierOperation.CASE_WORKSPACE, ("json", "typed-manifest"), ("case_id", "subject_id", "context_key", "variants"), ("normalize context key", "canonicalize variant identity", "retain source versions"), content_hash("adapter-case-manifest")),
        WorkspaceFrontierInputAdapter("adapter-cohort-records", WorkspaceFrontierAdapterKind.COHORT_RECORDS, WorkspaceFrontierOperation.COHORT_WORKSPACE, ("json", "record-stream"), ("evidence_id", "query_id", "context_key", "records"), ("normalize chromosome", "retain callable flag", "separate controls"), content_hash("adapter-cohort-records")),
        WorkspaceFrontierInputAdapter("adapter-variant-identity", WorkspaceFrontierAdapterKind.VARIANT_IDENTITY, WorkspaceFrontierOperation.VARIANT_EXPLORER, ("json", "canonical-variant"), ("case", "variant_id"), ("resolve exact ID", "withhold absent ID", "group declared links"), content_hash("adapter-variant-identity")),
        WorkspaceFrontierInputAdapter("adapter-interval-track", WorkspaceFrontierAdapterKind.INTERVAL_TRACK, WorkspaceFrontierOperation.REGULATORY_TRACK_BROWSER, ("bed", "narrowpeak", "gff3", "json"), ("source_id", "genome_build", "text", "context_key"), ("preserve coordinates", "retain row hash", "attach parse issues"), content_hash("adapter-interval-track")),
    )
    body = {"adapters": adapters}
    return WorkspaceFrontierAdapterRegistry(adapters=adapters, content_address=content_hash(body))


def adapt_workspace_frontier_input(adapter: WorkspaceFrontierInputAdapter, payload: Mapping[str, Any]) -> WorkspaceFrontierAdapterReceipt:
    inspected = adapter.inspect(payload)
    body = {"adapter_id": adapter.adapter_id, "input_address": content_hash(payload), "accepted": inspected["accepted"], "missing_fields": tuple(inspected["missing_fields"])}
    return WorkspaceFrontierAdapterReceipt(**body, content_address=content_hash(body))


__all__ = ["WorkspaceFrontierAdapterKind", "WorkspaceFrontierAdapterReceipt", "WorkspaceFrontierAdapterRegistry", "WorkspaceFrontierInputAdapter", "adapt_workspace_frontier_input", "default_workspace_frontier_adapters"]
