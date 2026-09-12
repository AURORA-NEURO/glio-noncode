"""Orchestration for case evaluation, review, replay, and local persistence."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping
from contextvars import ContextVar
from dataclasses import Field, dataclass, fields, replace
from datetime import datetime, timedelta
from math import isfinite
from pathlib import Path
from threading import Lock, RLock
from time import monotonic
from types import FunctionType, MethodType, ModuleType
from typing import Any, cast

from . import _callback_isolation as _callback_isolation_module
from ._callback_isolation import detached_callback_guard, runtime_callback_scope
from .adapters import (
    AdapterClaimAttribution,
    AdapterClaimCollectionReport,
    AdapterLimits,
    AdapterMetadata,
    AdapterRegistry,
    AdapterRegistrySnapshot,
    AdapterRegistrySnapshotEntry,
    AdapterResolutionItem,
    AdapterResolutionReport,
    RegistryEntry,
)
from .atlas import (
    AtlasBundle,
    AtlasObservation,
    AtlasQuery,
    AtlasReplayInputs,
    PublicAtlasRetriever,
)
from .data_sources import (
    MAX_ENRICHED_ELEMENTS,
    MAX_REFERENCE_FEATURES,
    MAX_REFERENCE_RECEIPTS,
    MAX_REFERENCE_VARIANTS,
    MAX_REFERENCE_WARNINGS,
    EncodeRestClient,
    EnrichmentResult,
    EnsemblRestClient,
    FetchReceipt,
    PublicReferenceRetriever,
    RateLimiter,
    ReferenceBundle,
    ReferenceRetrievalLimits,
    RetryPolicy,
    SequenceSlice,
    SourceCache,
    SourceCatalog,
    SourceClient,
    SourceSpec,
    UcscRestClient,
    UrllibTransport,
)
from .errors import PolicyViolation, StoreError, ValidationError
from .events import MAX_EVENT_PAYLOAD_BYTES, MAX_EVENT_RECORD_BYTES, EventLog, RuntimeEvent
from .evidence import AggregateSupport, EvidenceGraph, EvidenceGraphLimits
from .experiments import ExperimentPlanner, ExperimentPlanningLimits
from .expression_claims import (
    RNA_CONSEQUENCE_CHANNEL,
    validate_rna_consequence,
)
from .expression_claims import (
    public_projection as rna_claim_public_projection,
)
from .expression_evidence import RNAConsequenceEvidence
from .hypotheses import BuiltHypotheses, HypothesisBuilder, HypothesisWorkLimits
from .models import (
    CandidateElement,
    CaseManifest,
    Dossier,
    EdgeType,
    EvidenceClaim,
    ExperimentOption,
    Hypothesis,
    HypothesisEdge,
    ReferenceContext,
    ResearchStatus,
    ReviewDecision,
    ReviewState,
    VariantIdentity,
)
from .policy import PolicyDecision, PolicyLimits, ResearchPolicy
from .reference_interval_index import ReferenceIndexQuery, ReferenceIndexQueryReport
from .reference_track_adapters import (
    DeclaredReferenceTrackAdapter,
    ReferenceTrackAdapterRegistry,
    ReferenceTrackMetadata,
    ReferenceTrackQueryReport,
    ReferenceTrackReading,
)
from .replay import ReplayReport, ReplayVerifier
from .scoring import element_relevance
from .sequence_inference import (
    MotifDefinition,
    MotifHit,
    MotifScanner,
    SequenceAnalysisResult,
    SequenceInference,
)
from .serialization import canonical_bytes, content_hash, freeze_json, jsonable, utc_now
from .storage import MAX_RUN_HISTORY_ENTRIES, ObjectStore, RunStore
from .uncertainty import (
    DomainProfile,
    OODAssessment,
    OutOfDomainDetector,
    UncertaintyComponent,
    UncertaintyPropagator,
    UncertaintyReport,
)
from .validation import (
    ContractValidator,
    ReleaseGate,
    ValidationIssue,
    ValidationLimits,
    ValidationReport,
)

_MAX_RUNTIME_RNA_INPUT_BYTES = 64 * 1024 * 1024
_MAX_RUNTIME_SOURCE_CLOSURE_BYTES = 256 * 1024 * 1024
_MAX_RUNTIME_RNA_CONSEQUENCES = 10_000
_MAX_RUNTIME_RNA_ROW_BYTES = 64 * 1024
_MAX_RUNTIME_RNA_REASON_CODES = 256
_MAX_RUNTIME_RNA_REASON_CODE_CHARACTERS = 128
_LOCK_TYPE = type(Lock())
_RLOCK_TYPE = type(RLock())
_ACTIVE_EVALUATION_RUNTIME_IDS: ContextVar[frozenset[int]] = ContextVar(
    "glio_noncode_active_evaluation_runtime_ids",
    default=frozenset(),
)
_RUNTIME_INSTANCE_FIELDS = frozenset(
    {
        "store",
        "builder",
        "planner",
        "policy",
        "validator",
        "release_gate",
        "reference_retriever",
        "atlas_retriever",
        "adapter_registry",
        "_rna_input_max_bytes",
        "_source_closure_max_bytes",
        "_logs",
        "_evaluation_lock",
        "_evaluation_active",
    }
)
_ATLAS_EVENT_EMPTY_PAYLOAD_BYTES = len(
    canonical_bytes(
        {
            "replay_input_addresses": [],
            "bundle_addresses": [],
            "claim_count": 0,
            "warnings": [],
        }
    )
)
_ATLAS_EVENT_ADDRESS_ITEM_BYTES = len(canonical_bytes("sha256:" + "0" * 64))
_DATACLASS_FIELD_ATTRIBUTE_NAMES = tuple(cast(Any, Field).__slots__)
_EVALUATION_SEMANTIC_MODULE_MAPPINGS = (
    ("glio_noncode.context", frozenset({"_WEIGHTS"})),
    ("glio_noncode.expression_claims", frozenset({"_STATE_MAP"})),
    ("glio_noncode.policy", frozenset({"_CONFUSABLE_ASCII"})),
    ("glio_noncode.sequence_inference", frozenset({"_IUPAC"})),
)
_EVALUATION_SEMANTIC_CLASS_MAPPINGS = (
    (UcscRestClient, frozenset({"_assemblies"})),
)
_ADAPTER_INPUT_VERSION_KEYS = (
    "adapter_input_manifest",
    "adapter_registry_snapshot",
    "adapter_resolution_report",
    "adapter_claim_collection_report",
)
_RESERVED_NATIVE_EVIDENCE_PRODUCERS = frozenset(
    {
        "deterministic_runtime",
        "deterministic_rna_claim_bridge",
        "deterministic_sequence_inference",
        "public_atlas_retriever",
    }
)
_ADAPTER_EVENT_FIELDS = frozenset(
    {
        "adapter_ids",
        "base_input_address",
        "effective_input_address",
        "registry_bundle_address",
        "registry_address",
        "resolution_bundle_address",
        "resolution_address",
        "claim_collection_bundle_address",
        "claim_collection_address",
        "resolved_element_count",
        "attribution_count",
        "claim_count",
        "source_bundle_addresses",
    }
)
_REFERENCE_EVENT_FIELDS = frozenset(
    {
        "submitted_input_address",
        "effective_input_address",
        "bundle_addresses",
        "receipt_count",
        "warnings",
    }
)
_ATLAS_EVENT_FIELDS = frozenset(
    {"replay_input_addresses", "bundle_addresses", "claim_count", "warnings"}
)
_FunctionGuardState = tuple[Any, ...]
_DataclassFieldGuardState = tuple[
    object,
    type[Any],
    tuple[tuple[str, object], ...],
]
_MappingGuardState = tuple[
    dict[Any, Any],
    tuple[tuple[Any, Any], ...],
]
_ClassGuardState = tuple[
    type[Any],
    tuple[tuple[str, object], ...],
    tuple[_FunctionGuardState, ...],
    tuple[_MappingGuardState, ...],
    tuple[_DataclassFieldGuardState, ...],
]
_EvaluationGuardState = tuple[
    dict[str, object],
    tuple[tuple[str, object], ...],
    tuple[_FunctionGuardState, ...],
    tuple[_MappingGuardState, ...],
    tuple[
        tuple[
            dict[str, object],
            tuple[tuple[str, object], ...],
            tuple[_FunctionGuardState, ...],
            tuple[_MappingGuardState, ...],
        ],
        ...,
    ],
    tuple[_ClassGuardState, ...],
]
_EVALUATION_DEPENDENCY_CLASSES: tuple[type[Any], ...] = (
    AdapterClaimAttribution,
    AdapterClaimCollectionReport,
    AdapterLimits,
    AdapterMetadata,
    AdapterRegistry,
    AdapterRegistrySnapshot,
    AdapterRegistrySnapshotEntry,
    AdapterResolutionItem,
    AdapterResolutionReport,
    AggregateSupport,
    AtlasBundle,
    AtlasObservation,
    AtlasQuery,
    AtlasReplayInputs,
    BuiltHypotheses,
    CandidateElement,
    CaseManifest,
    ContractValidator,
    DeclaredReferenceTrackAdapter,
    Dossier,
    DomainProfile,
    EncodeRestClient,
    EnrichmentResult,
    EnsemblRestClient,
    EvidenceClaim,
    EvidenceGraph,
    EvidenceGraphLimits,
    EventLog,
    ExperimentOption,
    ExperimentPlanner,
    ExperimentPlanningLimits,
    Hypothesis,
    HypothesisEdge,
    HypothesisBuilder,
    HypothesisWorkLimits,
    MotifDefinition,
    MotifHit,
    MotifScanner,
    OODAssessment,
    ObjectStore,
    OutOfDomainDetector,
    PolicyDecision,
    PolicyLimits,
    PublicAtlasRetriever,
    PublicReferenceRetriever,
    RateLimiter,
    ReferenceBundle,
    ReferenceContext,
    ReferenceIndexQuery,
    ReferenceIndexQueryReport,
    ReferenceRetrievalLimits,
    ReferenceTrackAdapterRegistry,
    ReferenceTrackMetadata,
    ReferenceTrackQueryReport,
    ReferenceTrackReading,
    ReleaseGate,
    ReplayReport,
    ReplayVerifier,
    ResearchPolicy,
    RetryPolicy,
    RNAConsequenceEvidence,
    RunStore,
    RuntimeEvent,
    SequenceAnalysisResult,
    SequenceInference,
    SequenceSlice,
    SourceCache,
    SourceCatalog,
    SourceClient,
    SourceSpec,
    FetchReceipt,
    UcscRestClient,
    UrllibTransport,
    ValidationIssue,
    ValidationLimits,
    ValidationReport,
    VariantIdentity,
    UncertaintyComponent,
    UncertaintyPropagator,
    UncertaintyReport,
)
_SNAPSHOT_PREDECESSOR_VERSION = "snapshot-predecessor-v1"
_SNAPSHOT_PREDECESSOR_FIELDS = frozenset(
    {
        "version",
        "run_id",
        "previous_event_address",
        "previous_dossier_address",
        "binding_address",
    }
)


@dataclass(frozen=True, slots=True)
class _HypothesisLimitsSnapshot:
    max_targets_per_element: int
    max_work_items: int
    max_rna_consequences: int
    max_external_claims: int


@dataclass(frozen=True, slots=True)
class _ExperimentLimitsSnapshot:
    max_hypotheses: int
    max_edges_per_hypothesis: int
    max_total_edges: int


@dataclass(frozen=True, slots=True)
class _PolicyLimitsSnapshot:
    max_text_items: int
    max_text_characters: int
    max_total_characters: int
    max_pattern_matches: int


@dataclass(frozen=True, slots=True)
class _ClassNamespaceSnapshot:
    target: type[Any]
    attributes: tuple[tuple[str, object], ...]
    function_states: tuple[_FunctionGuardState, ...]
    mapping_states: tuple[_MappingConfigurationSnapshot, ...]
    dataclass_field_states: tuple[_FrozenConfigurationSnapshot, ...]


@dataclass(frozen=True, slots=True)
class _ModuleNamespaceSnapshot:
    namespace: dict[str, object]
    attributes: tuple[tuple[str, object], ...]
    function_states: tuple[_FunctionGuardState, ...]
    mapping_states: tuple[_MappingConfigurationSnapshot, ...]


@dataclass(frozen=True, slots=True)
class _InstanceNamespaceSnapshot:
    target: object
    target_type: type[Any]
    namespace: dict[str, object]
    attributes: tuple[tuple[str, object], ...]


@dataclass(frozen=True, slots=True)
class _MappingConfigurationSnapshot:
    target: dict[Any, Any]
    items: tuple[tuple[Any, Any], ...]


@dataclass(frozen=True, slots=True)
class _FrozenConfigurationSnapshot:
    target: object
    target_type: type[Any]
    attributes: tuple[tuple[str, object], ...]


@dataclass(frozen=True, slots=True)
class _AtlasTrackAdapterConfigurationSnapshot:
    target: DeclaredReferenceTrackAdapter
    canonical: DeclaredReferenceTrackAdapter
    encoded: bytes


@dataclass(frozen=True, slots=True)
class _RateLimiterConfigurationSnapshot:
    target: RateLimiter
    target_type: type[Any]
    namespace: dict[str, object]
    interval_seconds: float
    lock: object
    next_allowed: float


@dataclass(frozen=True, slots=True)
class _SourceConfigurationSnapshot:
    instances: tuple[_InstanceNamespaceSnapshot, ...]
    mappings: tuple[_MappingConfigurationSnapshot, ...]
    frozen_configurations: tuple[_FrozenConfigurationSnapshot, ...]
    rate_limiters: tuple[_RateLimiterConfigurationSnapshot, ...]


@dataclass(frozen=True, slots=True)
class _RunStoreSnapshot:
    store: RunStore
    object_store: ObjectStore
    root: Path
    runs: Path
    locks: Path
    run_lock: object
    object_root: Path
    objects: Path
    object_locks: Path
    object_lock: object


@dataclass(frozen=True, slots=True)
class _AdapterRegistryConfigurationSnapshot:
    registry: AdapterRegistry
    limits_object: AdapterLimits
    limits: AdapterLimits
    limits_address: str
    entries: dict[str, RegistryEntry]
    lock: Any


@dataclass(frozen=True, slots=True)
class _EvaluationConfigurationSnapshot:
    runtime_instance_configuration: _InstanceNamespaceSnapshot
    configured_instance_namespaces: tuple[_InstanceNamespaceSnapshot, ...]
    builder: HypothesisBuilder
    builder_limits_object: HypothesisWorkLimits
    builder_limits: _HypothesisLimitsSnapshot
    planner: ExperimentPlanner
    planner_limits_object: ExperimentPlanningLimits
    planner_limits: _ExperimentLimitsSnapshot
    validator: ContractValidator
    validator_limits_object: ValidationLimits
    validator_limits: ValidationLimits
    policy: ResearchPolicy
    policy_limits_object: PolicyLimits
    policy_limits: _PolicyLimitsSnapshot
    release_gate: ReleaseGate
    release_validator: ContractValidator
    release_validator_limits_object: ValidationLimits
    release_validator_limits: ValidationLimits
    run_store: _RunStoreSnapshot
    runtime_module_namespace: _ModuleNamespaceSnapshot
    dependency_module_namespaces: tuple[_ModuleNamespaceSnapshot, ...]
    dependency_class_namespaces: tuple[_ClassNamespaceSnapshot, ...]
    reference_retriever: PublicReferenceRetriever | None
    reference_retriever_configuration: _InstanceNamespaceSnapshot | None
    reference_source_configuration: _SourceConfigurationSnapshot | None
    atlas_retriever: PublicAtlasRetriever | None
    atlas_retriever_configuration: _InstanceNamespaceSnapshot | None
    atlas_source_configurations: tuple[_SourceConfigurationSnapshot, ...]
    atlas_nested_instances: tuple[_InstanceNamespaceSnapshot, ...]
    atlas_nested_mappings: tuple[_MappingConfigurationSnapshot, ...]
    atlas_frozen_configurations: tuple[_FrozenConfigurationSnapshot, ...]
    atlas_track_configurations: tuple[_AtlasTrackAdapterConfigurationSnapshot, ...]
    adapter_registry: AdapterRegistry | None
    adapter_registry_configuration: _AdapterRegistryConfigurationSnapshot | None
    selected_adapter_ids: tuple[str, ...]
    selected_adapter_snapshot: AdapterRegistrySnapshot | None
    selected_adapter_entries: tuple[RegistryEntry, ...]
    rna_input_max_bytes: int
    source_closure_max_bytes: int
    evaluation_lock: object
    evaluation_active: bool


_SNAPSHOT_SUCCESSOR_EVENT_TYPES = frozenset({"review_assigned", "review_recorded"})
_REVIEW_ASSIGNMENT_FIELDS = frozenset(
    {
        "assignment_id",
        "run_id",
        "case_id",
        "reviewer",
        "queue_id",
        "due_at",
        "note",
        "created_at",
        "content_address",
    }
)
_RNA_CONSEQUENCE_RECORD_FIELDS = frozenset(
    {
        "schema_version",
        "prediction_id",
        "prediction_address",
        "variant_id",
        "feature_id",
        "context_key",
        "predicted_direction",
        "state",
        "expression_state",
        "expression_direction",
        "expression_robust_z",
        "expression_result_address",
        "allelic_state",
        "allelic_direction",
        "allelic_log2_ratio",
        "allelic_q_value",
        "allelic_result_address",
        "reason_codes",
        "content_address",
    }
)
_VERIFIED_RUN_RECORD_FIELDS = frozenset(
    {
        "run_id",
        "input_address",
        "event_address",
        "event_history",
        "dossier_address",
        "dossier_history",
    }
)


def _runtime_sha256_address(value: object, label: str) -> str:
    if (
        type(value) is not str
        or len(value) != 71
        or not value.startswith("sha256:")
        or any(character not in "0123456789abcdef" for character in value[7:])
    ):
        raise ValidationError(f"{label} must be a canonical sha256 content address")
    return value


@dataclass(frozen=True, slots=True)
class VerifiedRunSnapshot:
    """Detached, typed closure over one replay-verified current run."""

    run_record: Mapping[str, Any]
    manifest: CaseManifest
    event_record: Mapping[str, Any]
    dossier: Dossier
    replay: ReplayReport

    def __post_init__(self) -> None:
        if type(self.run_record) is not dict or set(self.run_record) != _VERIFIED_RUN_RECORD_FIELDS:
            raise ValidationError(
                "verified snapshot run_record must be an exact current run object"
            )
        if type(self.manifest) is not CaseManifest:
            raise ValidationError("verified snapshot manifest must be an exact CaseManifest")
        if type(self.event_record) is not dict:
            raise ValidationError("verified snapshot event_record must be an exact object")
        if type(self.dossier) is not Dossier:
            raise ValidationError("verified snapshot dossier must be an exact Dossier")
        if type(self.replay) is not ReplayReport:
            raise ValidationError("verified snapshot replay must be an exact ReplayReport")
        record = dict(self.run_record)
        run_id = record["run_id"]
        input_address = record["input_address"]
        event_address = record["event_address"]
        dossier_address = record["dossier_address"]
        if type(run_id) is not str or not run_id.startswith("run-") or len(run_id) > 128:
            raise ValidationError("verified snapshot run_id must be a bounded run identifier")
        for field, value in (
            ("input_address", input_address),
            ("event_address", event_address),
            ("dossier_address", dossier_address),
        ):
            _runtime_sha256_address(value, f"verified snapshot {field}")
        for history_field, current in (
            ("event_history", event_address),
            ("dossier_history", dossier_address),
        ):
            history = record[history_field]
            if (
                type(history) is not list
                or not history
                or len(history) > MAX_RUN_HISTORY_ENTRIES
                or any(type(item) is not str for item in history)
                or any(
                    _runtime_sha256_address(item, f"verified snapshot {history_field} entry")
                    != item
                    for item in history
                )
                or len(history) != len(set(history))
                or history[-1] != current
            ):
                raise ValidationError(
                    f"verified snapshot {history_field} must be a unique current-ended address list"
                )
        if len(record["event_history"]) > len(record["dossier_history"]):
            raise ValidationError(
                "verified snapshot event history cannot exceed its dossier history"
            )
        try:
            log = EventLog.from_record(
                self.event_record,
                expected_address=event_address,
            )
        except (TypeError, ValueError) as exc:
            raise ValidationError("verified snapshot event record is invalid") from exc
        if not log.verify():
            raise ValidationError("verified snapshot event record must contain a valid chain")
        event_record = log.to_record()
        dossier_record = self.dossier.to_dict()
        dossier_body = {
            key: value for key, value in dossier_record.items() if key != "content_address"
        }
        expected_replay = ReplayVerifier().verify(record, event_record, dossier_record)
        if (
            run_id != self.dossier.run_id
            or log.run_id != run_id
            or self.dossier.case_id != self.manifest.case_id
            or self.dossier.input_address != self.manifest.content_address
            or input_address != self.manifest.content_address
            or event_address != content_hash(event_record)
            or dossier_address != content_hash(dossier_body)
            or self.dossier.content_address != dossier_address
            or self.dossier.event_head != log.head
            or not expected_replay.event_chain_valid
            or not expected_replay.stored_dossier_matches_address
            or canonical_bytes(self.replay.to_dict()) != canonical_bytes(expected_replay.to_dict())
        ):
            raise ValidationError("verified snapshot artifacts do not form one replay-closed run")
        frozen_record = freeze_json(record, field="verified snapshot run_record")
        if not isinstance(frozen_record, Mapping):  # pragma: no cover - guarded above
            raise ValidationError("verified snapshot run_record must remain an object")
        object.__setattr__(self, "run_record", frozen_record)
        frozen_events = freeze_json(event_record, field="verified snapshot event_record")
        if not isinstance(frozen_events, Mapping):  # pragma: no cover - exact dict above
            raise ValidationError("verified snapshot event_record must remain an object")
        object.__setattr__(self, "event_record", frozen_events)

    @property
    def run_id(self) -> str:
        return self.dossier.run_id

    @property
    def event_log(self) -> EventLog:
        """Return a fresh mutable log detached from the verified snapshot."""

        raw = jsonable(self.event_record)
        if type(raw) is not dict:  # pragma: no cover - constructor invariant
            raise ValidationError("verified snapshot event_record copy must be an object")
        event_address = self.run_record.get("event_address")
        try:
            return EventLog.from_record(
                raw,
                expected_address=event_address if type(event_address) is str else None,
            )
        except (TypeError, ValueError) as exc:  # pragma: no cover - constructor invariant
            raise ValidationError("verified snapshot event log could not be detached") from exc

    def run_record_dict(self) -> dict[str, Any]:
        """Return a mutable canonical copy for compare-and-swap persistence."""

        value = jsonable(self.run_record)
        if type(value) is not dict:  # pragma: no cover - frozen mapping is guaranteed above
            raise ValidationError("verified snapshot run_record copy must be an object")
        return value


class CaseRuntime:
    """Coordinate typed inputs, deterministic builders, policy, and storage."""

    def __init__(
        self,
        data_root: str | Path = ".glio",
        *,
        reference_retriever: PublicReferenceRetriever | None = None,
        atlas_retriever: PublicAtlasRetriever | None = None,
        adapter_registry: AdapterRegistry | None = None,
        hypothesis_limits: HypothesisWorkLimits | None = None,
        experiment_limits: ExperimentPlanningLimits | None = None,
        rna_input_max_bytes: int = _MAX_RUNTIME_RNA_INPUT_BYTES,
        source_closure_max_bytes: int = _MAX_RUNTIME_SOURCE_CLOSURE_BYTES,
    ) -> None:
        if type(rna_input_max_bytes) is not int or not 1 <= rna_input_max_bytes <= (
            _MAX_RUNTIME_RNA_INPUT_BYTES
        ):
            raise ValidationError(
                "rna_input_max_bytes must be a positive integer no greater than "
                f"{_MAX_RUNTIME_RNA_INPUT_BYTES}"
            )
        if adapter_registry is not None and type(adapter_registry) is not AdapterRegistry:
            raise ValidationError("adapter_registry must be an exact AdapterRegistry")
        if (
            type(source_closure_max_bytes) is not int
            or not 1 <= source_closure_max_bytes <= _MAX_RUNTIME_SOURCE_CLOSURE_BYTES
        ):
            raise ValidationError(
                "source_closure_max_bytes must be a positive integer no greater than "
                f"{_MAX_RUNTIME_SOURCE_CLOSURE_BYTES}"
            )
        builder = HypothesisBuilder(
            limits=HypothesisWorkLimits() if hypothesis_limits is None else hypothesis_limits
        )
        planner = ExperimentPlanner(
            limits=ExperimentPlanningLimits() if experiment_limits is None else experiment_limits
        )
        self.store = RunStore(data_root)
        self.builder = builder
        self.planner = planner
        self.policy = ResearchPolicy()
        self.validator = ContractValidator()
        self.release_gate = ReleaseGate(self.policy)
        self.reference_retriever = reference_retriever
        self.atlas_retriever = atlas_retriever
        self.adapter_registry = adapter_registry
        self._rna_input_max_bytes = rna_input_max_bytes
        self._source_closure_max_bytes = source_closure_max_bytes
        self._logs: dict[str, EventLog] = {}
        self._evaluation_lock = RLock()
        self._evaluation_active = False

    @staticmethod
    def _bounded_configuration_integer(
        value: object,
        *,
        label: str,
        ceiling: int,
    ) -> int:
        if type(value) is not int or not 1 <= value <= ceiling:
            raise ValidationError(f"{label} must be a positive integer no greater than {ceiling}")
        return value

    @staticmethod
    def _snapshot_function_states(
        descriptors: Iterable[object],
    ) -> tuple[_FunctionGuardState, ...]:
        """Capture executable function internals without invoking descriptors."""

        functions: list[FunctionType] = []
        for descriptor in descriptors:
            if type(descriptor) is FunctionType:
                functions.append(descriptor)
            elif type(descriptor) in {staticmethod, classmethod}:
                wrapped_descriptor = cast(Any, descriptor)
                functions.append(wrapped_descriptor.__func__)
            elif type(descriptor) is property:
                functions.extend(
                    cast(FunctionType, function)
                    for function in (descriptor.fget, descriptor.fset, descriptor.fdel)
                    if function is not None
                )
        function_states: list[_FunctionGuardState] = []
        seen_functions: set[int] = set()
        function_index = 0
        while function_index < len(functions):
            function = functions[function_index]
            function_index += 1
            if id(function) in seen_functions:
                continue
            if len(seen_functions) >= 65_536:
                raise ValidationError("runtime semantic function graph exceeds limit")
            seen_functions.add(id(function))
            wrapped = vars(function).get("__wrapped__")
            if type(wrapped) is FunctionType:
                functions.append(wrapped)
            closure_states: list[tuple[object, bool, object | None]] = []
            for cell in function.__closure__ or ():
                try:
                    value = cell.cell_contents
                except ValueError:
                    closure_states.append((cell, False, None))
                else:
                    closure_states.append((cell, True, value))
                    if type(value) is FunctionType:
                        functions.append(value)
            kwdefaults = function.__kwdefaults__
            annotations = function.__annotations__
            function_dict = vars(function)
            function_states.append(
                (
                    function,
                    function.__code__,
                    function.__defaults__,
                    kwdefaults,
                    () if kwdefaults is None else tuple(sorted(kwdefaults.items())),
                    annotations,
                    tuple(sorted(annotations.items())),
                    function_dict,
                    tuple(function_dict.items()),
                    tuple(closure_states),
                )
            )
        return tuple(function_states)

    @classmethod
    def _snapshot_module_namespace(
        cls,
        namespace: dict[str, object],
    ) -> _ModuleNamespaceSnapshot:
        """Pin module bindings, functions, and constant mapping contents."""

        attributes = tuple(sorted(namespace.items()))
        module_name = namespace.get("__name__")
        if type(module_name) is not str:
            raise ValidationError("runtime dependency module name is invalid")
        protected_mapping_names = dict(_EVALUATION_SEMANTIC_MODULE_MAPPINGS).get(
            module_name,
            frozenset(),
        )
        for mapping_name in protected_mapping_names:
            if type(namespace.get(mapping_name)) is not dict:
                raise ValidationError(
                    f"runtime semantic mapping is missing or invalid: {module_name}.{mapping_name}"
                )
        mapping_states = tuple(
            _MappingConfigurationSnapshot(
                target=value,
                items=tuple(value.items()),
            )
            for name, value in attributes
            if type(value) is dict and name in protected_mapping_names
        )
        return _ModuleNamespaceSnapshot(
            namespace=namespace,
            attributes=attributes,
            function_states=cls._snapshot_function_states(namespace.values()),
            mapping_states=mapping_states,
        )

    @classmethod
    def _snapshot_class_namespace(cls, target: type[Any]) -> _ClassNamespaceSnapshot:
        """Pin an exact class shell, executable internals, and semantic mappings."""

        try:
            namespace = vars(target)
            attributes = tuple(sorted(namespace.items()))
            function_states = cls._snapshot_function_states(
                descriptor for _name, descriptor in attributes
            )
            protected_mapping_names = set(
                dict(_EVALUATION_SEMANTIC_CLASS_MAPPINGS).get(target, frozenset())
            )
            if "__dataclass_fields__" in namespace:
                protected_mapping_names.add("__dataclass_fields__")
            for mapping_name in protected_mapping_names:
                if type(namespace.get(mapping_name)) is not dict:
                    raise ValidationError(
                        "runtime dependency class semantic mapping is missing or invalid: "
                        f"{target.__module__}.{target.__qualname__}.{mapping_name}"
                    )
            mapping_states = tuple(
                _MappingConfigurationSnapshot(
                    target=value,
                    items=tuple(value.items()),
                )
                for name, value in attributes
                if type(value) is dict and name in protected_mapping_names
            )
            dataclass_field_states: tuple[_FrozenConfigurationSnapshot, ...] = ()
            dataclass_fields = namespace.get("__dataclass_fields__")
            if type(dataclass_fields) is dict:
                if any(type(item) is not Field for item in dataclass_fields.values()):
                    raise ValidationError("runtime dataclass field registry is invalid")
                dataclass_field_states = tuple(
                    _FrozenConfigurationSnapshot(
                        target=item,
                        target_type=Field,
                        attributes=tuple(
                            (name, getattr(item, name))
                            for name in _DATACLASS_FIELD_ATTRIBUTE_NAMES
                        ),
                    )
                    for item in dataclass_fields.values()
                )
        except Exception as exc:  # noqa: BLE001 - mutable class boundary
            if isinstance(exc, ValidationError):
                raise
            raise ValidationError("runtime dependency class is mutated or invalid") from exc
        if any(type(name) is not str for name, _value in attributes):
            raise ValidationError("runtime dependency class has invalid attribute names")
        return _ClassNamespaceSnapshot(
            target=target,
            attributes=attributes,
            function_states=tuple(function_states),
            mapping_states=mapping_states,
            dataclass_field_states=dataclass_field_states,
        )

    @classmethod
    def _snapshot_builder_limits(
        cls,
        builder: object,
    ) -> tuple[HypothesisBuilder, HypothesisWorkLimits, _HypothesisLimitsSnapshot]:
        if type(builder) is not HypothesisBuilder:
            raise ValidationError("runtime builder must be an exact HypothesisBuilder")
        try:
            state = vars(builder)
            limits = builder.limits
            if type(state) is not dict or set(state) != {"limits"}:
                raise ValidationError("runtime builder has non-canonical instance state")
            if type(limits) is not HypothesisWorkLimits:
                raise ValidationError("runtime builder limits must be exact HypothesisWorkLimits")
            snapshot = _HypothesisLimitsSnapshot(
                max_targets_per_element=cls._bounded_configuration_integer(
                    limits.max_targets_per_element,
                    label="runtime builder max_targets_per_element",
                    ceiling=128,
                ),
                max_work_items=cls._bounded_configuration_integer(
                    limits.max_work_items,
                    label="runtime builder max_work_items",
                    ceiling=10_000,
                ),
                max_rna_consequences=cls._bounded_configuration_integer(
                    limits.max_rna_consequences,
                    label="runtime builder max_rna_consequences",
                    ceiling=10_000,
                ),
                max_external_claims=cls._bounded_configuration_integer(
                    limits.max_external_claims,
                    label="runtime builder max_external_claims",
                    ceiling=10_000,
                ),
            )
        except Exception as exc:  # noqa: BLE001 - mutable public runtime state
            if isinstance(exc, ValidationError):
                raise
            raise ValidationError("runtime builder is mutated or invalid") from exc
        return builder, limits, snapshot

    @classmethod
    def _snapshot_planner_limits(
        cls,
        planner: object,
    ) -> tuple[ExperimentPlanner, ExperimentPlanningLimits, _ExperimentLimitsSnapshot]:
        if type(planner) is not ExperimentPlanner:
            raise ValidationError("runtime planner must be an exact ExperimentPlanner")
        try:
            state = vars(planner)
            limits = planner.limits
            if type(state) is not dict or set(state) != {"limits"}:
                raise ValidationError("runtime planner has non-canonical instance state")
            if type(limits) is not ExperimentPlanningLimits:
                raise ValidationError(
                    "runtime planner limits must be exact ExperimentPlanningLimits"
                )
            snapshot = _ExperimentLimitsSnapshot(
                max_hypotheses=cls._bounded_configuration_integer(
                    limits.max_hypotheses,
                    label="runtime planner max_hypotheses",
                    ceiling=10_000,
                ),
                max_edges_per_hypothesis=cls._bounded_configuration_integer(
                    limits.max_edges_per_hypothesis,
                    label="runtime planner max_edges_per_hypothesis",
                    ceiling=1_024,
                ),
                max_total_edges=cls._bounded_configuration_integer(
                    limits.max_total_edges,
                    label="runtime planner max_total_edges",
                    ceiling=20_000,
                ),
            )
        except Exception as exc:  # noqa: BLE001 - mutable public runtime state
            if isinstance(exc, ValidationError):
                raise
            raise ValidationError("runtime planner is mutated or invalid") from exc
        return planner, limits, snapshot

    @staticmethod
    def _snapshot_validation_limits(limits: object, label: str) -> ValidationLimits:
        if type(limits) is not ValidationLimits:
            raise ValidationError(f"{label} must be exact ValidationLimits")
        try:
            values = {item.name: getattr(limits, item.name) for item in fields(ValidationLimits)}
            return ValidationLimits(**values)
        except Exception as exc:  # noqa: BLE001 - forged frozen values fail closed
            if isinstance(exc, ValidationError):
                raise
            raise ValidationError(f"{label} are mutated or invalid") from exc

    @classmethod
    def _snapshot_policy_limits(cls, limits: object) -> _PolicyLimitsSnapshot:
        if type(limits) is not PolicyLimits:
            raise ValidationError("runtime policy limits must be exact PolicyLimits")
        try:
            return _PolicyLimitsSnapshot(
                max_text_items=cls._bounded_configuration_integer(
                    limits.max_text_items,
                    label="runtime policy max_text_items",
                    ceiling=500_000,
                ),
                max_text_characters=cls._bounded_configuration_integer(
                    limits.max_text_characters,
                    label="runtime policy max_text_characters",
                    ceiling=65_536,
                ),
                max_total_characters=cls._bounded_configuration_integer(
                    limits.max_total_characters,
                    label="runtime policy max_total_characters",
                    ceiling=33_554_432,
                ),
                max_pattern_matches=cls._bounded_configuration_integer(
                    limits.max_pattern_matches,
                    label="runtime policy max_pattern_matches",
                    ceiling=100_000,
                ),
            )
        except Exception as exc:  # noqa: BLE001 - forged frozen values fail closed
            if isinstance(exc, ValidationError):
                raise
            raise ValidationError("runtime policy limits are mutated or invalid") from exc

    @staticmethod
    def _snapshot_run_store(store: object) -> _RunStoreSnapshot:
        if type(store) is not RunStore:
            raise ValidationError("runtime store must be an exact RunStore")
        try:
            state = vars(store)
            if type(state) is not dict or set(state) != {
                "root",
                "store",
                "runs",
                "_locks",
                "_lock",
            }:
                raise ValidationError("runtime store has non-canonical instance state")
            object_store = store.store
            if type(object_store) is not ObjectStore:
                raise ValidationError("runtime object store must be an exact ObjectStore")
            object_state = vars(object_store)
            if type(object_state) is not dict or set(object_state) != {
                "root",
                "objects",
                "_locks",
                "_lock",
            }:
                raise ValidationError("runtime object store has non-canonical instance state")
            path_values = (
                store.root,
                store.runs,
                store._locks,  # noqa: SLF001 - runtime integrity boundary
                object_store.root,
                object_store.objects,
                object_store._locks,  # noqa: SLF001 - runtime integrity boundary
            )
            if any(not isinstance(value, Path) for value in path_values):
                raise ValidationError("runtime store paths are invalid")
            if (
                store.runs != store.root / "runs"
                or store._locks != store.root / ".locks" / "runs"  # noqa: SLF001
                or object_store.root != store.root
                or object_store.objects != store.root / "objects"
                or object_store._locks  # noqa: SLF001
                != store.root / ".locks" / "objects"
            ):
                raise ValidationError("runtime store paths are inconsistent")
            return _RunStoreSnapshot(
                store=store,
                object_store=object_store,
                root=store.root,
                runs=store.runs,
                locks=store._locks,  # noqa: SLF001 - runtime integrity boundary
                run_lock=store._lock,  # noqa: SLF001 - runtime integrity boundary
                object_root=object_store.root,
                objects=object_store.objects,
                object_locks=object_store._locks,  # noqa: SLF001 - integrity boundary
                object_lock=object_store._lock,  # noqa: SLF001 - integrity boundary
            )
        except Exception as exc:  # noqa: BLE001 - mutable persistence boundary
            if isinstance(exc, ValidationError):
                raise
            raise ValidationError("runtime store is mutated or invalid") from exc

    @staticmethod
    def _snapshot_adapter_registry_configuration(
        registry: object,
    ) -> _AdapterRegistryConfigurationSnapshot | None:
        """Capture the mutable registry shell without constraining unrelated entries."""

        if registry is None:
            return None
        if type(registry) is not AdapterRegistry:
            raise ValidationError("runtime adapter_registry must be an exact AdapterRegistry")
        try:
            state = vars(registry)
            if type(state) is not dict or set(state) != {
                "_limits",
                "_limits_address",
                "_entries",
                "_lock",
            }:
                raise ValidationError("runtime adapter registry has non-canonical instance state")
            limits_object = state["_limits"]
            if type(limits_object) is not AdapterLimits:
                raise ValidationError("runtime adapter registry limits are invalid")
            limits = AdapterLimits(**limits_object.to_dict())
            limits_address = state["_limits_address"]
            if type(limits_address) is not str or limits_address != content_hash(
                limits.to_dict(), prefix="adapter-limits"
            ):
                raise ValidationError("runtime adapter registry limits were mutated")
            entries = state["_entries"]
            if type(entries) is not dict or any(
                type(adapter_id) is not str or type(entry) is not RegistryEntry
                for adapter_id, entry in entries.items()
            ):
                raise ValidationError("runtime adapter registry entries are invalid")
            lock = state["_lock"]
            if type(lock) is not _RLOCK_TYPE:
                raise ValidationError("runtime adapter registry lock is invalid")
            return _AdapterRegistryConfigurationSnapshot(
                registry=registry,
                limits_object=limits_object,
                limits=limits,
                limits_address=limits_address,
                entries=entries,
                lock=lock,
            )
        except Exception as exc:  # noqa: BLE001 - mutable extension boundary
            if isinstance(exc, ValidationError):
                raise
            raise ValidationError("runtime adapter registry is mutated or invalid") from exc

    @staticmethod
    def _snapshot_builtin_retriever_configuration(
        retriever: object,
    ) -> _InstanceNamespaceSnapshot | None:
        """Pin exact built-in retriever fields while custom callbacks remain opaque."""

        retriever_type = type(retriever)
        if retriever_type not in {PublicReferenceRetriever, PublicAtlasRetriever}:
            return None
        try:
            namespace = vars(retriever)
            expected_fields = (
                {"client", "ensembl", "ucsc", "window_bp", "limits", "_lock"}
                if retriever_type is PublicReferenceRetriever
                else {
                    "_reference_retriever",
                    "_encode_client",
                    "_sequence_inference",
                    "_motifs",
                    "_uncertainty_propagator",
                    "_domain_profile",
                    "_track_adapters",
                    "_lock",
                }
            )
            if type(namespace) is not dict or set(namespace) != expected_fields:
                raise ValidationError("built-in retriever has non-canonical instance state")
            if type(namespace["_lock"]) is not _RLOCK_TYPE:
                raise ValidationError("built-in retriever lock is invalid")
            return _InstanceNamespaceSnapshot(
                target=retriever,
                target_type=retriever_type,
                namespace=namespace,
                attributes=tuple(sorted(namespace.items())),
            )
        except Exception as exc:  # noqa: BLE001 - mutable callback configuration
            if isinstance(exc, ValidationError):
                raise
            raise ValidationError("built-in retriever is mutated or invalid") from exc

    @staticmethod
    def _snapshot_source_configuration(
        provider: object,
    ) -> _SourceConfigurationSnapshot | None:
        """Pin configuration below exact built-in public-source providers."""

        provider_type = type(provider)
        if provider_type not in {PublicReferenceRetriever, EncodeRestClient}:
            return None
        try:
            instances: list[_InstanceNamespaceSnapshot] = []
            mappings: list[_MappingConfigurationSnapshot] = []
            frozen_configurations: list[_FrozenConfigurationSnapshot] = []
            rate_limiters: list[_RateLimiterConfigurationSnapshot] = []

            def capture_instance(
                target: object,
                expected_type: type[Any],
                expected_names: set[str],
                label: str,
            ) -> dict[str, object]:
                if type(target) is not expected_type:
                    raise ValidationError(f"built-in source {label} has an invalid type")
                namespace = vars(target)
                if type(namespace) is not dict or set(namespace) != expected_names:
                    raise ValidationError(
                        f"built-in source {label} has non-canonical instance state"
                    )
                instances.append(
                    _InstanceNamespaceSnapshot(
                        target=target,
                        target_type=expected_type,
                        namespace=namespace,
                        attributes=tuple(sorted(namespace.items())),
                    )
                )
                return namespace

            def capture_frozen(
                target: object,
                declared_type: type[Any],
                label: str,
                *,
                allow_subclass: bool = False,
            ) -> None:
                valid_type = (
                    isinstance(target, declared_type)
                    if allow_subclass
                    else type(target) is declared_type
                )
                if not valid_type:
                    raise ValidationError(f"built-in source {label} has an invalid type")
                attributes = tuple(
                    (item.name, getattr(target, item.name)) for item in fields(declared_type)
                )
                declared_type(**dict(attributes))
                frozen_configurations.append(
                    _FrozenConfigurationSnapshot(
                        target=target,
                        target_type=type(target),
                        attributes=attributes,
                    )
                )

            if provider_type is PublicReferenceRetriever:
                provider_state = vars(provider)
                if type(provider_state) is not dict or set(provider_state) != {
                    "client",
                    "ensembl",
                    "ucsc",
                    "window_bp",
                    "limits",
                    "_lock",
                }:
                    raise ValidationError(
                        "built-in public reference retriever has non-canonical instance state"
                    )
                client = provider_state["client"]
                if type(provider_state["_lock"]) is not _RLOCK_TYPE:
                    raise ValidationError("built-in public reference retriever lock is invalid")
                ensembl_state = capture_instance(
                    provider_state["ensembl"],
                    EnsemblRestClient,
                    {"client"},
                    "Ensembl client",
                )
                ucsc_state = capture_instance(
                    provider_state["ucsc"],
                    UcscRestClient,
                    {"client"},
                    "UCSC client",
                )
                if ensembl_state["client"] is not client or ucsc_state["client"] is not client:
                    raise ValidationError(
                        "built-in public reference clients do not share their SourceClient"
                    )
                capture_frozen(
                    provider_state["limits"],
                    ReferenceRetrievalLimits,
                    "reference retrieval limits",
                )
            else:
                encode_state = capture_instance(
                    provider,
                    EncodeRestClient,
                    {"client"},
                    "ENCODE client",
                )
                client = encode_state["client"]

            client_state = capture_instance(
                client,
                SourceClient,
                {
                    "catalog",
                    "transport",
                    "retry_policy",
                    "timeout_seconds",
                    "cache_ttl_seconds",
                    "user_agent",
                    "cache",
                    "_limiters",
                },
                "client",
            )
            catalog_state = capture_instance(
                client_state["catalog"],
                SourceCatalog,
                {"_specs", "_lock"},
                "catalog",
            )
            if type(catalog_state["_lock"]) is not _RLOCK_TYPE:
                raise ValidationError("built-in source catalog lock is invalid")
            specs = catalog_state["_specs"]
            if type(specs) is not dict or any(
                type(source_id) is not str
                or not isinstance(spec, SourceSpec)
                or spec.source_id != source_id
                for source_id, spec in specs.items()
            ):
                raise ValidationError("built-in source catalog entries are invalid")
            spec_items = tuple(sorted(specs.items()))
            mappings.append(_MappingConfigurationSnapshot(target=specs, items=spec_items))
            for _source_id, spec in spec_items:
                capture_frozen(spec, SourceSpec, "catalog entry", allow_subclass=True)

            cache_state = capture_instance(
                client_state["cache"],
                SourceCache,
                {"root", "_locks", "_lock"},
                "cache",
            )
            if (
                not isinstance(cache_state["root"], Path)
                or not isinstance(cache_state["_locks"], Path)
                or cache_state["_locks"] != cache_state["root"] / ".locks"
                or type(cache_state["_lock"]) is not _RLOCK_TYPE
            ):
                raise ValidationError("built-in source cache configuration is invalid")

            transport = client_state["transport"]
            if type(transport) is UrllibTransport:
                transport_state = capture_instance(
                    transport,
                    UrllibTransport,
                    {"max_response_bytes"},
                    "urllib transport",
                )
                maximum = transport_state["max_response_bytes"]
                if type(maximum) is not int or maximum < 1_024:
                    raise ValidationError("built-in source transport limit is invalid")

            retry_policy = client_state["retry_policy"]
            if isinstance(retry_policy, RetryPolicy):
                capture_frozen(
                    retry_policy,
                    RetryPolicy,
                    "retry policy",
                    allow_subclass=True,
                )

            limiters = client_state["_limiters"]
            if type(limiters) is not dict or set(limiters) != set(specs) or any(
                type(source_id) is not str or type(limiter) is not RateLimiter
                for source_id, limiter in limiters.items()
            ):
                raise ValidationError("built-in source rate limiters are invalid")
            limiter_items = tuple(sorted(limiters.items()))
            mappings.append(
                _MappingConfigurationSnapshot(target=limiters, items=limiter_items)
            )
            for _source_id, limiter in limiter_items:
                limiter_state = vars(limiter)
                if type(limiter_state) is not dict or set(limiter_state) != {
                    "interval_seconds",
                    "_lock",
                    "_next_allowed",
                }:
                    raise ValidationError(
                        "built-in source rate limiter has non-canonical instance state"
                    )
                limiter_lock = limiter_state["_lock"]
                if type(limiter_lock) is not _LOCK_TYPE:
                    raise ValidationError("built-in source rate limiter configuration is invalid")
                with cast(Any, limiter_lock):
                    interval = object.__getattribute__(limiter, "interval_seconds")
                    next_allowed = object.__getattribute__(limiter, "_next_allowed")
                    observed_at = monotonic()
                if (
                    type(interval) not in {int, float}
                    or not 0.0 < float(interval) <= 60.0
                    or type(next_allowed) not in {int, float}
                    or not isfinite(float(next_allowed))
                    or float(next_allowed) < 0.0
                    or float(next_allowed) > observed_at + float(interval)
                ):
                    raise ValidationError("built-in source rate limiter configuration is invalid")
                rate_limiters.append(
                    _RateLimiterConfigurationSnapshot(
                        target=limiter,
                        target_type=RateLimiter,
                        namespace=limiter_state,
                        interval_seconds=float(interval),
                        lock=limiter_lock,
                        next_allowed=float(next_allowed),
                    )
                )

            assemblies = vars(UcscRestClient)["_assemblies"]
            if type(assemblies) is not dict or any(
                type(name) is not str or type(value) is not str
                for name, value in assemblies.items()
            ):
                raise ValidationError("built-in UCSC assembly mapping is invalid")
            mappings.append(
                _MappingConfigurationSnapshot(
                    target=assemblies,
                    items=tuple(assemblies.items()),
                )
            )
            return _SourceConfigurationSnapshot(
                instances=tuple(instances),
                mappings=tuple(mappings),
                frozen_configurations=tuple(frozen_configurations),
                rate_limiters=tuple(rate_limiters),
            )
        except Exception as exc:  # noqa: BLE001 - nested mutable source configuration
            if isinstance(exc, ValidationError):
                raise
            raise ValidationError("built-in source configuration is mutated or invalid") from exc

    @classmethod
    def _snapshot_atlas_nested_configuration(
        cls,
        retriever: object,
    ) -> tuple[
        tuple[_InstanceNamespaceSnapshot, ...],
        tuple[_MappingConfigurationSnapshot, ...],
        tuple[_FrozenConfigurationSnapshot, ...],
        tuple[_AtlasTrackAdapterConfigurationSnapshot, ...],
        tuple[_SourceConfigurationSnapshot, ...],
    ]:
        """Pin mutable state below an exact built-in atlas retriever shell."""

        if type(retriever) is not PublicAtlasRetriever:
            return (), (), (), (), ()
        try:
            atlas_state = vars(retriever)
            nested_instances: list[_InstanceNamespaceSnapshot] = []
            nested_mappings: list[_MappingConfigurationSnapshot] = []
            frozen_configurations: list[_FrozenConfigurationSnapshot] = []
            track_configurations: list[_AtlasTrackAdapterConfigurationSnapshot] = []
            source_configurations: list[_SourceConfigurationSnapshot] = []

            def capture_instance(
                target: object,
                expected_type: type[Any],
                expected_names: set[str],
                label: str,
            ) -> None:
                if type(target) is not expected_type:
                    raise ValidationError(f"built-in atlas {label} has an invalid type")
                namespace = vars(target)
                if type(namespace) is not dict or set(namespace) != expected_names:
                    raise ValidationError(
                        f"built-in atlas {label} has non-canonical instance state"
                    )
                nested_instances.append(
                    _InstanceNamespaceSnapshot(
                        target=target,
                        target_type=expected_type,
                        namespace=namespace,
                        attributes=tuple(sorted(namespace.items())),
                    )
                )

            sequence_inference = atlas_state["_sequence_inference"]
            if type(sequence_inference) is SequenceInference:
                capture_instance(
                    sequence_inference,
                    SequenceInference,
                    {"scanner"},
                    "sequence inference",
                )
                capture_instance(
                    vars(sequence_inference)["scanner"],
                    MotifScanner,
                    set(),
                    "motif scanner",
                )

            uncertainty = atlas_state["_uncertainty_propagator"]
            if type(uncertainty) is UncertaintyPropagator:
                capture_instance(
                    uncertainty,
                    UncertaintyPropagator,
                    set(),
                    "uncertainty propagator",
                )

            nested_reference = atlas_state["_reference_retriever"]
            reference_state = cls._snapshot_builtin_retriever_configuration(nested_reference)
            if reference_state is not None:
                nested_instances.append(reference_state)
            reference_source_state = cls._snapshot_source_configuration(nested_reference)
            if reference_source_state is not None:
                source_configurations.append(reference_source_state)

            encode_source_state = cls._snapshot_source_configuration(
                atlas_state["_encode_client"]
            )
            if encode_source_state is not None:
                source_configurations.append(encode_source_state)

            track_registry = atlas_state["_track_adapters"]
            if track_registry is not None:
                capture_instance(
                    track_registry,
                    ReferenceTrackAdapterRegistry,
                    {"_adapters"},
                    "track adapter registry",
                )
                adapters = vars(track_registry)["_adapters"]
                if type(adapters) is not dict or any(
                    type(adapter_id) is not str
                    or type(adapter) is not DeclaredReferenceTrackAdapter
                    or adapter.metadata.adapter_id != adapter_id
                    for adapter_id, adapter in adapters.items()
                ):
                    raise ValidationError(
                        "built-in atlas track adapter registry contents are invalid"
                    )
                nested_mappings.append(
                    _MappingConfigurationSnapshot(
                        target=adapters,
                        items=tuple(sorted(adapters.items())),
                    )
                )
                for adapter_id in sorted(adapters):
                    adapter = adapters[adapter_id]
                    record = adapter.to_dict()
                    canonical = DeclaredReferenceTrackAdapter.from_dict(record)
                    encoded = canonical_bytes(record)
                    if canonical_bytes(canonical.to_dict()) != encoded:
                        raise ValidationError(
                            "built-in atlas track adapter does not round-trip exactly"
                        )
                    track_configurations.append(
                        _AtlasTrackAdapterConfigurationSnapshot(
                            target=adapter,
                            canonical=canonical,
                            encoded=encoded,
                        )
                    )

            motifs = atlas_state["_motifs"]
            if type(motifs) is not tuple or any(
                type(motif) is not MotifDefinition for motif in motifs
            ):
                raise ValidationError("built-in atlas motifs are invalid")
            frozen_configurations.extend(
                _FrozenConfigurationSnapshot(
                    target=motif,
                    target_type=MotifDefinition,
                    attributes=tuple(
                        (item.name, getattr(motif, item.name)) for item in fields(motif)
                    ),
                )
                for motif in motifs
            )

            domain_profile = atlas_state["_domain_profile"]
            if domain_profile is not None:
                if type(domain_profile) is not DomainProfile:
                    raise ValidationError("built-in atlas domain profile is invalid")
                frozen_configurations.append(
                    _FrozenConfigurationSnapshot(
                        target=domain_profile,
                        target_type=DomainProfile,
                        attributes=tuple(
                            (item.name, getattr(domain_profile, item.name))
                            for item in fields(domain_profile)
                        ),
                    )
                )
            return (
                tuple(nested_instances),
                tuple(nested_mappings),
                tuple(frozen_configurations),
                tuple(track_configurations),
                tuple(source_configurations),
            )
        except Exception as exc:  # noqa: BLE001 - nested mutable callback configuration
            if isinstance(exc, ValidationError):
                raise
            raise ValidationError(
                "built-in atlas nested configuration is mutated or invalid"
            ) from exc

    def _capture_evaluation_configuration(
        self,
        selected_adapter_ids: tuple[str, ...] = (),
    ) -> _EvaluationConfigurationSnapshot:
        runtime_type = type(self)
        if runtime_type is not CaseRuntime:
            raise ValidationError("runtime must be an exact CaseRuntime")
        runtime_namespace = vars(self)
        if (
            type(runtime_namespace) is not dict
            or frozenset(runtime_namespace) != _RUNTIME_INSTANCE_FIELDS
        ):
            raise ValidationError("runtime has non-canonical instance state")
        module_namespace = globals()
        runtime_module_namespace = self._snapshot_module_namespace(module_namespace)
        runtime_guard_classes = (
            runtime_type,
            _HypothesisLimitsSnapshot,
            _ExperimentLimitsSnapshot,
            _PolicyLimitsSnapshot,
            _ClassNamespaceSnapshot,
            _ModuleNamespaceSnapshot,
            _InstanceNamespaceSnapshot,
            _MappingConfigurationSnapshot,
            _FrozenConfigurationSnapshot,
            _AtlasTrackAdapterConfigurationSnapshot,
            _RateLimiterConfigurationSnapshot,
            _SourceConfigurationSnapshot,
            _RunStoreSnapshot,
            _AdapterRegistryConfigurationSnapshot,
            _EvaluationConfigurationSnapshot,
        )
        dependency_class_namespaces: list[_ClassNamespaceSnapshot] = []
        dependency_module_namespaces: list[_ModuleNamespaceSnapshot] = []
        seen_module_namespaces = {id(module_namespace)}
        seen_classes: set[int] = set()
        pending_module_snapshots = [runtime_module_namespace]
        pending_class_snapshots: list[_ClassNamespaceSnapshot] = []
        pending_function_states: list[_FunctionGuardState] = []
        seen_functions: set[int] = set()
        graph_limit = 65_536

        def is_package_namespace(namespace: Mapping[str, object]) -> bool:
            package = namespace.get("__package__")
            return type(package) is str and (
                package == "glio_noncode" or package.startswith("glio_noncode.")
            )

        def queue_function_states(states: Iterable[_FunctionGuardState]) -> None:
            for state in states:
                function = state[0]
                if type(function) is not FunctionType:
                    raise ValidationError("runtime semantic function graph is invalid")
                if id(function) in seen_functions:
                    continue
                if len(seen_functions) >= graph_limit:
                    raise ValidationError("runtime semantic function graph exceeds limit")
                seen_functions.add(id(function))
                pending_function_states.append(state)

        def add_module(namespace: dict[str, object]) -> None:
            if id(namespace) in seen_module_namespaces:
                return
            if not is_package_namespace(namespace):
                return
            if len(seen_module_namespaces) >= graph_limit:
                raise ValidationError("runtime semantic module graph exceeds limit")
            seen_module_namespaces.add(id(namespace))
            snapshot = self._snapshot_module_namespace(namespace)
            dependency_module_namespaces.append(snapshot)
            pending_module_snapshots.append(snapshot)
            queue_function_states(snapshot.function_states)

        def add_class(target: type[Any], *, required: bool = False) -> None:
            if id(target) in seen_classes:
                return
            owner = getattr(target, "__module__", "")
            if not required and not (
                type(owner) is str
                and (owner == "glio_noncode" or owner.startswith("glio_noncode."))
            ):
                return
            if len(seen_classes) >= graph_limit:
                raise ValidationError("runtime semantic class graph exceeds limit")
            seen_classes.add(id(target))
            snapshot = self._snapshot_class_namespace(target)
            dependency_class_namespaces.append(snapshot)
            pending_class_snapshots.append(snapshot)
            queue_function_states(snapshot.function_states)

        queue_function_states(runtime_module_namespace.function_states)
        for target in (*runtime_guard_classes, *_EVALUATION_DEPENDENCY_CLASSES):
            add_class(target, required=True)

        module_index = 0
        class_index = 0
        function_index = 0
        while (
            module_index < len(pending_module_snapshots)
            or class_index < len(pending_class_snapshots)
            or function_index < len(pending_function_states)
        ):
            candidates: Iterable[object]
            if module_index < len(pending_module_snapshots):
                snapshot = pending_module_snapshots[module_index]
                module_index += 1
                candidates = (value for _name, value in snapshot.attributes)
            elif class_index < len(pending_class_snapshots):
                class_snapshot = pending_class_snapshots[class_index]
                class_index += 1
                candidates = (value for _name, value in class_snapshot.attributes)
            else:
                function_state = pending_function_states[function_index]
                function_index += 1
                function = cast(FunctionType, function_state[0])
                add_module(function.__globals__)
                function_candidates: list[object] = []
                defaults = cast(tuple[object, ...] | None, function_state[2])
                if defaults is not None:
                    function_candidates.extend(defaults)
                function_candidates.extend(
                    value
                    for _name, value in cast(tuple[tuple[str, object], ...], function_state[4])
                )
                function_candidates.extend(
                    value
                    for _name, value in cast(tuple[tuple[str, object], ...], function_state[6])
                )
                function_candidates.extend(
                    value
                    for _name, value in cast(tuple[tuple[str, object], ...], function_state[8])
                )
                function_candidates.extend(
                    value
                    for _cell, had_value, value in cast(
                        tuple[tuple[object, bool, object | None], ...],
                        function_state[9],
                    )
                    if had_value
                )
                candidates = iter(function_candidates)
            for candidate in candidates:
                if type(candidate) is FunctionType:
                    queue_function_states(self._snapshot_function_states((candidate,)))
                elif isinstance(candidate, type):
                    add_class(candidate)
                elif type(candidate) is ModuleType:
                    module_candidate = cast(ModuleType, candidate)
                    module_candidate_namespace = vars(module_candidate)
                    if type(module_candidate_namespace) is dict:
                        add_module(module_candidate_namespace)
        builder, builder_limits_object, builder_limits = self._snapshot_builder_limits(self.builder)
        planner, planner_limits_object, planner_limits = self._snapshot_planner_limits(self.planner)
        validator = self._require_exact_validator(self.validator, "runtime validator")
        validator_limits_object = validator.limits
        validator_limits = self._snapshot_validation_limits(
            validator_limits_object,
            "runtime validator limits",
        )
        self._require_exact_policy()
        policy = self.policy
        policy_limits_object = policy.limits
        policy_limits = self._snapshot_policy_limits(policy_limits_object)
        release_gate = self.release_gate
        if type(release_gate) is not ReleaseGate:
            raise ValidationError("runtime release_gate must be an exact ReleaseGate")
        try:
            release_state = vars(release_gate)
            if type(release_state) is not dict or set(release_state) != {
                "policy",
                "validator",
            }:
                raise ValidationError("runtime release_gate has non-canonical instance state")
            if release_gate.policy is not policy:
                raise ValidationError("runtime release_gate is not bound to the runtime policy")
            release_validator = self._require_exact_validator(
                release_gate.validator,
                "runtime release_gate validator",
            )
            release_validator_limits_object = release_validator.limits
            release_validator_limits = self._snapshot_validation_limits(
                release_validator_limits_object,
                "runtime release_gate validator limits",
            )
        except Exception as exc:  # noqa: BLE001 - mutable public runtime state
            if isinstance(exc, ValidationError):
                raise
            raise ValidationError("runtime release_gate is mutated or invalid") from exc
        adapter_registry = self.adapter_registry
        adapter_registry_configuration = self._snapshot_adapter_registry_configuration(
            adapter_registry
        )
        if type(selected_adapter_ids) is not tuple or any(
            type(item) is not str for item in selected_adapter_ids
        ):
            raise ValidationError("selected adapter IDs must be an exact tuple of strings")
        selected_adapter_snapshot: AdapterRegistrySnapshot | None = None
        selected_adapter_entries: tuple[RegistryEntry, ...] = ()
        if selected_adapter_ids:
            if adapter_registry is None:
                raise ValidationError("adapter_ids require a configured AdapterRegistry")
            selected_adapter_snapshot, selected_adapter_entries = AdapterRegistry.selected_entries(
                adapter_registry,
                selected_adapter_ids,
            )
        rna_input_max_bytes = self._bounded_configuration_integer(
            self._rna_input_max_bytes,
            label="runtime rna_input_max_bytes",
            ceiling=_MAX_RUNTIME_RNA_INPUT_BYTES,
        )
        source_closure_max_bytes = self._bounded_configuration_integer(
            self._source_closure_max_bytes,
            label="runtime source_closure_max_bytes",
            ceiling=_MAX_RUNTIME_SOURCE_CLOSURE_BYTES,
        )
        evaluation_lock = self._evaluation_lock
        if type(evaluation_lock) is not _RLOCK_TYPE:
            raise ValidationError("runtime evaluation lock is invalid")
        evaluation_active = self._evaluation_active
        if type(evaluation_active) is not bool:
            raise ValidationError("runtime evaluation state is invalid")
        run_store = self._snapshot_run_store(self.store)
        reference_retriever = self.reference_retriever
        atlas_retriever = self.atlas_retriever
        reference_retriever_configuration = self._snapshot_builtin_retriever_configuration(
            reference_retriever
        )
        reference_source_configuration = self._snapshot_source_configuration(
            reference_retriever
        )
        atlas_retriever_configuration = self._snapshot_builtin_retriever_configuration(
            atlas_retriever
        )
        (
            atlas_nested_instances,
            atlas_nested_mappings,
            atlas_frozen_configurations,
            atlas_track_configurations,
            atlas_source_configurations,
        ) = self._snapshot_atlas_nested_configuration(atlas_retriever)
        runtime_instance_configuration = _InstanceNamespaceSnapshot(
            target=self,
            target_type=CaseRuntime,
            namespace=runtime_namespace,
            attributes=tuple(sorted(runtime_namespace.items())),
        )
        configured_targets: list[tuple[object, type[Any]]] = [
            (builder, HypothesisBuilder),
            (planner, ExperimentPlanner),
            (validator, ContractValidator),
            (policy, ResearchPolicy),
            (release_gate, ReleaseGate),
            (release_validator, ContractValidator),
            (run_store.store, RunStore),
            (run_store.object_store, ObjectStore),
        ]
        if adapter_registry is not None:
            configured_targets.append((adapter_registry, AdapterRegistry))
        configured_instance_namespaces = tuple(
            _InstanceNamespaceSnapshot(
                target=target,
                target_type=target_type,
                namespace=vars(target),
                attributes=tuple(sorted(vars(target).items())),
            )
            for target, target_type in configured_targets
        )
        return _EvaluationConfigurationSnapshot(
            runtime_instance_configuration=runtime_instance_configuration,
            configured_instance_namespaces=configured_instance_namespaces,
            builder=builder,
            builder_limits_object=builder_limits_object,
            builder_limits=builder_limits,
            planner=planner,
            planner_limits_object=planner_limits_object,
            planner_limits=planner_limits,
            validator=validator,
            validator_limits_object=validator_limits_object,
            validator_limits=validator_limits,
            policy=policy,
            policy_limits_object=policy_limits_object,
            policy_limits=policy_limits,
            release_gate=release_gate,
            release_validator=release_validator,
            release_validator_limits_object=release_validator_limits_object,
            release_validator_limits=release_validator_limits,
            run_store=run_store,
            runtime_module_namespace=runtime_module_namespace,
            dependency_module_namespaces=tuple(dependency_module_namespaces),
            dependency_class_namespaces=tuple(dependency_class_namespaces),
            reference_retriever=reference_retriever,
            reference_retriever_configuration=reference_retriever_configuration,
            reference_source_configuration=reference_source_configuration,
            atlas_retriever=atlas_retriever,
            atlas_retriever_configuration=atlas_retriever_configuration,
            atlas_source_configurations=atlas_source_configurations,
            atlas_nested_instances=atlas_nested_instances,
            atlas_nested_mappings=atlas_nested_mappings,
            atlas_frozen_configurations=atlas_frozen_configurations,
            atlas_track_configurations=atlas_track_configurations,
            adapter_registry=adapter_registry,
            adapter_registry_configuration=adapter_registry_configuration,
            selected_adapter_ids=selected_adapter_ids,
            selected_adapter_snapshot=selected_adapter_snapshot,
            selected_adapter_entries=selected_adapter_entries,
            rna_input_max_bytes=rna_input_max_bytes,
            source_closure_max_bytes=source_closure_max_bytes,
            evaluation_lock=evaluation_lock,
            evaluation_active=evaluation_active,
        )

    @staticmethod
    def _evaluation_guard_state(
        expected: _EvaluationConfigurationSnapshot,
    ) -> _EvaluationGuardState:
        """Detach the integrity guard from callback-mutable runtime classes."""

        module_snapshot = expected.runtime_module_namespace
        return (
            module_snapshot.namespace,
            module_snapshot.attributes,
            module_snapshot.function_states,
            tuple((snapshot.target, snapshot.items) for snapshot in module_snapshot.mapping_states),
            tuple(
                (
                    snapshot.namespace,
                    snapshot.attributes,
                    snapshot.function_states,
                    tuple((mapping.target, mapping.items) for mapping in snapshot.mapping_states),
                )
                for snapshot in expected.dependency_module_namespaces
            ),
            tuple(
                (
                    snapshot.target,
                    snapshot.attributes,
                    snapshot.function_states,
                    tuple((mapping.target, mapping.items) for mapping in snapshot.mapping_states),
                    tuple(
                        (
                            field_state.target,
                            field_state.target_type,
                            field_state.attributes,
                        )
                        for field_state in snapshot.dataclass_field_states
                    ),
                )
                for snapshot in expected.dependency_class_namespaces
            ),
        )

    def _assert_evaluation_configuration(
        self,
        expected: _EvaluationConfigurationSnapshot,
        guard_state: _EvaluationGuardState | None = None,
    ) -> None:
        # Validate module bindings and class shells without dynamically resolving
        # another CaseRuntime method: the runtime's own descriptors are part of
        # the trust boundary and may be the thing an untrusted callback replaced.
        if guard_state is None:
            guard_state = self._evaluation_guard_state(expected)
        (
            module_namespace,
            module_attributes,
            module_function_states,
            module_mapping_states,
            dependency_module_states,
            class_states,
        ) = guard_state
        expected_module = dict(module_attributes)
        error_type = expected_module["ValidationError"]

        def function_state_unchanged(state: _FunctionGuardState) -> bool:
            (
                function,
                code,
                defaults,
                kwdefaults,
                kwdefault_items,
                annotations,
                annotation_items,
                function_dict,
                function_dict_items,
                closure_states,
            ) = state
            try:
                if (
                    function.__code__ is not code
                    or function.__defaults__ is not defaults
                    or function.__kwdefaults__ is not kwdefaults
                    or function.__annotations__ is not annotations
                    or vars(function) is not function_dict
                ):
                    return False
                if kwdefaults is not None and (
                    set(kwdefaults) != {name for name, _value in kwdefault_items}
                    or any(kwdefaults[name] is not value for name, value in kwdefault_items)
                ):
                    return False
                if set(annotations) != {name for name, _value in annotation_items} or any(
                    annotations[name] is not value for name, value in annotation_items
                ):
                    return False
                if set(function_dict) != {name for name, _value in function_dict_items} or any(
                    function_dict[name] is not value for name, value in function_dict_items
                ):
                    return False
                current_closure = function.__closure__ or ()
                if len(current_closure) != len(closure_states):
                    return False
                for current_cell, (expected_cell, had_value, expected_value) in zip(
                    current_closure,
                    closure_states,
                    strict=True,
                ):
                    if current_cell is not expected_cell:
                        return False
                    try:
                        current_value = current_cell.cell_contents
                    except ValueError:
                        if had_value:
                            return False
                    else:
                        if not had_value or current_value is not expected_value:
                            return False
            except Exception:  # noqa: BLE001 - hostile function mutation
                return False
            return True

        def module_state_unchanged(
            namespace: dict[str, object],
            attributes: tuple[tuple[str, object], ...],
            function_states: tuple[_FunctionGuardState, ...],
            mapping_states: tuple[_MappingGuardState, ...],
        ) -> bool:
            expected_attributes = dict(attributes)
            return (
                set(namespace) == set(expected_attributes)
                and all(namespace[name] is value for name, value in attributes)
                and all(function_state_unchanged(state) for state in function_states)
                and all(
                    set(mapping) == {name for name, _value in items}
                    and all(mapping[name] is value for name, value in items)
                    for mapping, items in mapping_states
                )
            )

        try:
            module_unchanged = (
                module_namespace is expected.runtime_module_namespace.namespace
                and all(
                    module_state_unchanged(
                        namespace,
                        attributes,
                        function_states,
                        mapping_states,
                    )
                    for namespace, attributes, function_states, mapping_states in (
                        (
                            module_namespace,
                            module_attributes,
                            module_function_states,
                            module_mapping_states,
                        ),
                        *dependency_module_states,
                    )
                )
            )
        except Exception as exc:  # noqa: BLE001 - hostile module mutation
            raise error_type(  # type: ignore[operator]
                "runtime evaluation configuration changed during untrusted work"
            ) from exc
        if not module_unchanged:
            raise error_type(  # type: ignore[operator]
                "runtime evaluation configuration changed during untrusted work"
            )
        for target, attributes, function_states, mapping_states, field_states in class_states:
            try:
                current_namespace = vars(target)
                expected_namespace = dict(attributes)
                class_unchanged = (
                    set(current_namespace) == set(expected_namespace)
                    and all(current_namespace[name] is value for name, value in attributes)
                    and all(function_state_unchanged(state) for state in function_states)
                    and all(
                        set(mapping) == {key for key, _value in items}
                        and all(mapping[key] is value for key, value in items)
                        for mapping, items in mapping_states
                    )
                    and all(
                        type(field) is field_type
                        and all(
                            getattr(field, name) is value
                            for name, value in field_attributes
                        )
                        for field, field_type, field_attributes in field_states
                    )
                )
            except Exception as exc:  # noqa: BLE001 - hostile class mutation
                raise error_type(  # type: ignore[operator]
                    "runtime evaluation configuration changed during untrusted work"
                ) from exc
            if not class_unchanged:
                raise error_type(  # type: ignore[operator]
                    "runtime evaluation configuration changed during untrusted work"
                )
        expected_runtime_instance = expected.runtime_instance_configuration
        try:
            runtime_namespace = vars(self)
            expected_runtime_attributes = dict(expected_runtime_instance.attributes)
            runtime_instance_unchanged = (
                expected_runtime_instance.target is self
                and expected_runtime_instance.target_type is CaseRuntime
                and type(self) is expected_runtime_instance.target_type
                and expected_runtime_instance.namespace is runtime_namespace
                and set(runtime_namespace) == set(expected_runtime_attributes)
                and all(
                    runtime_namespace[name] is value
                    for name, value in expected_runtime_instance.attributes
                )
            )
        except Exception as exc:  # noqa: BLE001 - hostile instance mutation
            raise error_type(  # type: ignore[operator]
                "runtime evaluation configuration changed during untrusted work"
            ) from exc
        if not runtime_instance_unchanged:
            raise error_type(  # type: ignore[operator]
                "runtime evaluation configuration changed during untrusted work"
            )
        current = CaseRuntime._capture_evaluation_configuration(
            self,
            expected.selected_adapter_ids,
        )
        current_guard_state = CaseRuntime._evaluation_guard_state(current)
        (
            current_module_namespace,
            current_module_attributes,
            current_module_function_states,
            current_module_mapping_states,
            current_dependency_module_states,
            current_class_states,
        ) = current_guard_state
        module_namespaces_unchanged = (
            current_module_namespace is module_namespace
            and len(current_module_attributes) == len(module_attributes)
            and all(
                current_name == expected_name and current_value is expected_value
                for (current_name, current_value), (expected_name, expected_value) in zip(
                    current_module_attributes,
                    module_attributes,
                    strict=True,
                )
            )
            and len(current_module_function_states) == len(module_function_states)
            and all(function_state_unchanged(state) for state in module_function_states)
            and len(current_module_mapping_states) == len(module_mapping_states)
            and all(
                current_mapping is expected_mapping
                and len(current_items) == len(expected_items)
                and all(
                    current_name == expected_name and current_value is expected_value
                    for (current_name, current_value), (
                        expected_name,
                        expected_value,
                    ) in zip(current_items, expected_items, strict=True)
                )
                for (current_mapping, current_items), (
                    expected_mapping,
                    expected_items,
                ) in zip(
                    current_module_mapping_states,
                    module_mapping_states,
                    strict=True,
                )
            )
            and len(current_dependency_module_states) == len(dependency_module_states)
            and all(
                current_namespace is expected_namespace
                and len(current_attributes) == len(expected_attributes)
                and all(
                    current_name == expected_name and current_value is expected_value
                    for (current_name, current_value), (
                        expected_name,
                        expected_value,
                    ) in zip(
                        current_attributes,
                        expected_attributes,
                        strict=True,
                    )
                )
                and len(current_functions) == len(expected_functions)
                and all(function_state_unchanged(state) for state in expected_functions)
                and len(current_mappings) == len(expected_mappings)
                and all(
                    current_mapping is expected_mapping
                    and len(current_items) == len(expected_items)
                    and all(
                        current_name == expected_name and current_value is expected_value
                        for (current_name, current_value), (
                            expected_name,
                            expected_value,
                        ) in zip(current_items, expected_items, strict=True)
                    )
                    for (current_mapping, current_items), (
                        expected_mapping,
                        expected_items,
                    ) in zip(current_mappings, expected_mappings, strict=True)
                )
                for (
                    current_namespace,
                    current_attributes,
                    current_functions,
                    current_mappings,
                ), (
                    expected_namespace,
                    expected_attributes,
                    expected_functions,
                    expected_mappings,
                ) in zip(
                    current_dependency_module_states,
                    dependency_module_states,
                    strict=True,
                )
            )
        )
        for target, attributes, function_states, mapping_states, field_states in class_states:
            try:
                current_namespace = vars(target)
                expected_namespace = dict(attributes)
                class_unchanged = (
                    set(current_namespace) == set(expected_namespace)
                    and all(current_namespace[name] is value for name, value in attributes)
                    and all(function_state_unchanged(state) for state in function_states)
                    and all(
                        set(mapping) == {key for key, _value in items}
                        and all(mapping[key] is value for key, value in items)
                        for mapping, items in mapping_states
                    )
                    and all(
                        type(field) is field_type
                        and all(
                            getattr(field, name) is value
                            for name, value in field_attributes
                        )
                        for field, field_type, field_attributes in field_states
                    )
                )
            except Exception as exc:  # noqa: BLE001 - hostile class mutation
                raise error_type(  # type: ignore[operator]
                    "runtime evaluation configuration changed during untrusted work"
                ) from exc
            if not class_unchanged:
                raise error_type(  # type: ignore[operator]
                    "runtime evaluation configuration changed during untrusted work"
                )
        class_namespaces_unchanged = len(current_class_states) == len(class_states) and all(
            current_target is expected_target
            and len(current_attributes) == len(expected_attributes)
            and all(
                current_name == expected_name and current_value is expected_value
                for (current_name, current_value), (expected_name, expected_value) in zip(
                    current_attributes,
                    expected_attributes,
                    strict=True,
                )
            )
            and len(current_functions) == len(expected_functions)
            and all(function_state_unchanged(state) for state in expected_functions)
            and len(current_mappings) == len(expected_mappings)
            and all(
                current_mapping is expected_mapping
                and len(current_items) == len(expected_items)
                and all(
                    current_key == expected_key and current_value is expected_value
                    for (current_key, current_value), (expected_key, expected_value) in zip(
                        current_items,
                        expected_items,
                        strict=True,
                    )
                )
                for (current_mapping, current_items), (
                    expected_mapping,
                    expected_items,
                ) in zip(current_mappings, expected_mappings, strict=True)
            )
            and len(current_fields) == len(expected_fields)
            and all(
                current_field is expected_field
                and current_field_type is expected_field_type
                and len(current_field_attributes) == len(expected_field_attributes)
                and all(
                    current_name == expected_name and current_value is expected_value
                    for (current_name, current_value), (expected_name, expected_value) in zip(
                        current_field_attributes,
                        expected_field_attributes,
                        strict=True,
                    )
                )
                for (current_field, current_field_type, current_field_attributes), (
                    expected_field,
                    expected_field_type,
                    expected_field_attributes,
                ) in zip(current_fields, expected_fields, strict=True)
            )
            for (
                current_target,
                current_attributes,
                current_functions,
                current_mappings,
                current_fields,
            ), (
                expected_target,
                expected_attributes,
                expected_functions,
                expected_mappings,
                expected_fields,
            ) in zip(
                current_class_states,
                class_states,
                strict=True,
            )
        )
        expected_registry = expected.adapter_registry_configuration
        current_registry = current.adapter_registry_configuration
        registry_unchanged = (
            expected_registry is None
            and current_registry is None
            or expected_registry is not None
            and current_registry is not None
            and current_registry.registry is expected_registry.registry
            and current_registry.limits_object is expected_registry.limits_object
            and current_registry.limits == expected_registry.limits
            and current_registry.limits_address == expected_registry.limits_address
            and current_registry.entries is expected_registry.entries
            and current_registry.lock is expected_registry.lock
        )
        selected_adapters_unchanged = len(current.selected_adapter_entries) == len(
            expected.selected_adapter_entries
        ) and all(
            current_entry.adapter is expected_entry.adapter
            for current_entry, expected_entry in zip(
                current.selected_adapter_entries,
                expected.selected_adapter_entries,
                strict=True,
            )
        )

        def instance_namespace_unchanged(
            current_snapshot: _InstanceNamespaceSnapshot | None,
            expected_snapshot: _InstanceNamespaceSnapshot | None,
        ) -> bool:
            if current_snapshot is None or expected_snapshot is None:
                return current_snapshot is expected_snapshot
            return (
                current_snapshot.target is expected_snapshot.target
                and current_snapshot.target_type is expected_snapshot.target_type
                and type(current_snapshot.target) is expected_snapshot.target_type
                and current_snapshot.namespace is expected_snapshot.namespace
                and len(current_snapshot.attributes) == len(expected_snapshot.attributes)
                and all(
                    current_name == expected_name and current_value is expected_value
                    for (current_name, current_value), (
                        expected_name,
                        expected_value,
                    ) in zip(
                        current_snapshot.attributes,
                        expected_snapshot.attributes,
                        strict=True,
                    )
                )
            )

        def source_configuration_unchanged(
            current_snapshot: _SourceConfigurationSnapshot | None,
            expected_snapshot: _SourceConfigurationSnapshot | None,
        ) -> bool:
            if current_snapshot is None or expected_snapshot is None:
                return current_snapshot is expected_snapshot
            return (
                len(current_snapshot.instances) == len(expected_snapshot.instances)
                and all(
                    instance_namespace_unchanged(current_item, expected_item)
                    for current_item, expected_item in zip(
                        current_snapshot.instances,
                        expected_snapshot.instances,
                        strict=True,
                    )
                )
                and len(current_snapshot.mappings) == len(expected_snapshot.mappings)
                and all(
                    current_item.target is expected_item.target
                    and len(current_item.items) == len(expected_item.items)
                    and all(
                        current_key == expected_key and current_value is expected_value
                        for (current_key, current_value), (
                            expected_key,
                            expected_value,
                        ) in zip(
                            current_item.items,
                            expected_item.items,
                            strict=True,
                        )
                    )
                    for current_item, expected_item in zip(
                        current_snapshot.mappings,
                        expected_snapshot.mappings,
                        strict=True,
                    )
                )
                and len(current_snapshot.frozen_configurations)
                == len(expected_snapshot.frozen_configurations)
                and all(
                    current_item.target is expected_item.target
                    and current_item.target_type is expected_item.target_type
                    and type(current_item.target) is expected_item.target_type
                    and len(current_item.attributes) == len(expected_item.attributes)
                    and all(
                        current_name == expected_name and current_value is expected_value
                        for (current_name, current_value), (
                            expected_name,
                            expected_value,
                        ) in zip(
                            current_item.attributes,
                            expected_item.attributes,
                            strict=True,
                        )
                    )
                    for current_item, expected_item in zip(
                        current_snapshot.frozen_configurations,
                        expected_snapshot.frozen_configurations,
                        strict=True,
                    )
                )
                and len(current_snapshot.rate_limiters) == len(expected_snapshot.rate_limiters)
                and all(
                    current_item.target is expected_item.target
                    and current_item.target_type is expected_item.target_type
                    and type(current_item.target) is expected_item.target_type
                    and current_item.namespace is expected_item.namespace
                    and current_item.interval_seconds == expected_item.interval_seconds
                    and current_item.lock is expected_item.lock
                    for current_item, expected_item in zip(
                        current_snapshot.rate_limiters,
                        expected_snapshot.rate_limiters,
                        strict=True,
                    )
                )
            )

        configured_instances_unchanged = len(current.configured_instance_namespaces) == len(
            expected.configured_instance_namespaces
        ) and all(
            instance_namespace_unchanged(current_item, expected_item)
            for current_item, expected_item in zip(
                current.configured_instance_namespaces,
                expected.configured_instance_namespaces,
                strict=True,
            )
        )
        atlas_source_configurations_unchanged = len(
            current.atlas_source_configurations
        ) == len(expected.atlas_source_configurations) and all(
            source_configuration_unchanged(current_item, expected_item)
            for current_item, expected_item in zip(
                current.atlas_source_configurations,
                expected.atlas_source_configurations,
                strict=True,
            )
        )

        nested_instances_unchanged = len(current.atlas_nested_instances) == len(
            expected.atlas_nested_instances
        ) and all(
            instance_namespace_unchanged(current_item, expected_item)
            for current_item, expected_item in zip(
                current.atlas_nested_instances,
                expected.atlas_nested_instances,
                strict=True,
            )
        )
        nested_mappings_unchanged = len(current.atlas_nested_mappings) == len(
            expected.atlas_nested_mappings
        ) and all(
            current_item.target is expected_item.target
            and len(current_item.items) == len(expected_item.items)
            and all(
                current_name == expected_name and current_value is expected_value
                for (current_name, current_value), (
                    expected_name,
                    expected_value,
                ) in zip(current_item.items, expected_item.items, strict=True)
            )
            for current_item, expected_item in zip(
                current.atlas_nested_mappings,
                expected.atlas_nested_mappings,
                strict=True,
            )
        )
        frozen_configurations_unchanged = len(current.atlas_frozen_configurations) == len(
            expected.atlas_frozen_configurations
        ) and all(
            current_item.target is expected_item.target
            and current_item.target_type is expected_item.target_type
            and type(current_item.target) is expected_item.target_type
            and len(current_item.attributes) == len(expected_item.attributes)
            and all(
                current_name == expected_name and current_value is expected_value
                for (current_name, current_value), (
                    expected_name,
                    expected_value,
                ) in zip(
                    current_item.attributes,
                    expected_item.attributes,
                    strict=True,
                )
            )
            for current_item, expected_item in zip(
                current.atlas_frozen_configurations,
                expected.atlas_frozen_configurations,
                strict=True,
            )
        )
        track_configurations_unchanged = len(current.atlas_track_configurations) == len(
            expected.atlas_track_configurations
        ) and all(
            current_item.target is expected_item.target
            and current_item.encoded == expected_item.encoded
            for current_item, expected_item in zip(
                current.atlas_track_configurations,
                expected.atlas_track_configurations,
                strict=True,
            )
        )

        unchanged = (
            instance_namespace_unchanged(
                current.runtime_instance_configuration,
                expected.runtime_instance_configuration,
            )
            and configured_instances_unchanged
            and current.builder is expected.builder
            and module_namespaces_unchanged
            and class_namespaces_unchanged
            and current.builder_limits_object is expected.builder_limits_object
            and current.builder_limits == expected.builder_limits
            and current.planner is expected.planner
            and current.planner_limits_object is expected.planner_limits_object
            and current.planner_limits == expected.planner_limits
            and current.validator is expected.validator
            and current.validator_limits_object is expected.validator_limits_object
            and current.validator_limits == expected.validator_limits
            and current.policy is expected.policy
            and current.policy_limits_object is expected.policy_limits_object
            and current.policy_limits == expected.policy_limits
            and current.release_gate is expected.release_gate
            and current.release_validator is expected.release_validator
            and current.release_validator_limits_object is expected.release_validator_limits_object
            and current.release_validator_limits == expected.release_validator_limits
            and current.run_store == expected.run_store
            and current.reference_retriever is expected.reference_retriever
            and instance_namespace_unchanged(
                current.reference_retriever_configuration,
                expected.reference_retriever_configuration,
            )
            and source_configuration_unchanged(
                current.reference_source_configuration,
                expected.reference_source_configuration,
            )
            and current.atlas_retriever is expected.atlas_retriever
            and instance_namespace_unchanged(
                current.atlas_retriever_configuration,
                expected.atlas_retriever_configuration,
            )
            and nested_instances_unchanged
            and nested_mappings_unchanged
            and frozen_configurations_unchanged
            and track_configurations_unchanged
            and atlas_source_configurations_unchanged
            and current.adapter_registry is expected.adapter_registry
            and registry_unchanged
            and current.selected_adapter_ids == expected.selected_adapter_ids
            and current.selected_adapter_snapshot == expected.selected_adapter_snapshot
            and selected_adapters_unchanged
            and current.rna_input_max_bytes == expected.rna_input_max_bytes
            and current.source_closure_max_bytes == expected.source_closure_max_bytes
            and current.evaluation_lock is expected.evaluation_lock
            and current.evaluation_active is expected.evaluation_active
        )
        if not unchanged:
            raise ValidationError("runtime evaluation configuration changed during untrusted work")

    @staticmethod
    def _restore_frozen_fields(target: object, snapshot: Any) -> None:
        """Restore a forged frozen limits value without replacing its identity."""

        for item in fields(snapshot):
            object.__setattr__(target, item.name, getattr(snapshot, item.name))

    def _restore_evaluation_configuration(
        self,
        expected: _EvaluationConfigurationSnapshot,
        guard_state: _EvaluationGuardState,
        assert_configuration: Any,
    ) -> bool:
        """Restore a captured runtime configuration and report whether it drifted."""

        (
            module_namespace,
            module_attributes,
            module_function_states,
            module_mapping_states,
            dependency_module_states,
            class_states,
        ) = guard_state
        expected_module = dict(module_attributes)
        error_type = expected_module["ValidationError"]

        def restore_exact_type(target: object, target_type: type[Any]) -> None:
            if type(target) is not target_type:
                object.__setattr__(target, "__class__", target_type)
            if type(target) is not target_type:
                raise error_type(  # type: ignore[operator]
                    "runtime evaluation object type could not be restored"
                )

        def restore_instance_namespace(state: _InstanceNamespaceSnapshot) -> None:
            restore_exact_type(state.target, state.target_type)
            current_namespace = vars(state.target)
            if current_namespace is not state.namespace:
                object.__setattr__(state.target, "__dict__", state.namespace)
            state.namespace.clear()
            state.namespace.update(dict(state.attributes))

        try:
            assert_configuration(expected, guard_state)
        except Exception:  # noqa: BLE001 - invalid mutable state must be recoverable
            changed = True
        else:
            return False

        try:
            for namespace, attributes, _function_states, mapping_states in (
                (
                    module_namespace,
                    module_attributes,
                    module_function_states,
                    module_mapping_states,
                ),
                *dependency_module_states,
            ):
                expected_namespace = dict(attributes)
                current_names = set(namespace)
                for name in current_names - set(expected_namespace):
                    del namespace[name]
                for name, value in attributes:
                    if name not in namespace or namespace[name] is not value:
                        namespace[name] = value
                for mapping, items in mapping_states:
                    mapping.clear()
                    mapping.update(dict(items))
            for (
                target,
                attributes,
                _function_states,
                mapping_states,
                field_states,
            ) in class_states:
                expected_namespace = dict(attributes)
                current_names = set(vars(target))
                for name in current_names - set(expected_namespace):
                    delattr(target, name)
                for name, value in attributes:
                    if name not in vars(target) or vars(target)[name] is not value:
                        setattr(target, name, value)
                for mapping, items in mapping_states:
                    mapping.clear()
                    mapping.update(dict(items))
                for field, field_type, field_attributes in field_states:
                    restore_exact_type(field, field_type)
                    for name, value in field_attributes:
                        setattr(field, name, value)
            all_function_states = (
                *module_function_states,
                *(
                    function_state
                    for (
                        _namespace,
                        _attributes,
                        function_states,
                        _mapping_states,
                    ) in dependency_module_states
                    for function_state in function_states
                ),
                *(
                    function_state
                    for (
                        _target,
                        _attributes,
                        function_states,
                        _mapping_states,
                        _field_states,
                    ) in class_states
                    for function_state in function_states
                ),
            )
            restored_functions: set[int] = set()
            for state in all_function_states:
                (
                    function,
                    code,
                    defaults,
                    kwdefaults,
                    kwdefault_items,
                    annotations,
                    annotation_items,
                    function_dict,
                    function_dict_items,
                    closure_states,
                ) = state
                if id(function) in restored_functions:
                    continue
                restored_functions.add(id(function))
                function.__code__ = code
                function.__defaults__ = defaults
                function.__kwdefaults__ = kwdefaults
                if kwdefaults is not None:
                    kwdefaults.clear()
                    kwdefaults.update(dict(kwdefault_items))
                function.__annotations__ = annotations
                annotations.clear()
                annotations.update(dict(annotation_items))
                function.__dict__ = function_dict
                function_dict.clear()
                function_dict.update(dict(function_dict_items))
                current_closure = function.__closure__ or ()
                if len(current_closure) != len(closure_states):
                    raise error_type(  # type: ignore[operator]
                        "runtime evaluation function closure could not be restored"
                    )
                for current_cell, (expected_cell, had_value, value) in zip(
                    current_closure,
                    closure_states,
                    strict=True,
                ):
                    if current_cell is not expected_cell:
                        raise error_type(  # type: ignore[operator]
                            "runtime evaluation function closure could not be restored"
                        )
                    if had_value:
                        current_cell.cell_contents = value
                    else:
                        try:
                            del current_cell.cell_contents
                        except ValueError:
                            pass
            runtime_state = expected.runtime_instance_configuration
            restore_instance_namespace(runtime_state)
            for configured_state in expected.configured_instance_namespaces:
                restore_instance_namespace(configured_state)
            source_configurations = (
                (() if expected.reference_source_configuration is None else (
                    expected.reference_source_configuration,
                ))
                + expected.atlas_source_configurations
            )
            for source_state in source_configurations:
                for frozen_state in source_state.frozen_configurations:
                    restore_exact_type(frozen_state.target, frozen_state.target_type)
                    for name, value in frozen_state.attributes:
                        object.__setattr__(frozen_state.target, name, value)
                for mapping_state in source_state.mappings:
                    mapping_state.target.clear()
                    mapping_state.target.update(dict(mapping_state.items))
                for instance_state in source_state.instances:
                    restore_instance_namespace(instance_state)
                for limiter_state in source_state.rate_limiters:
                    with cast(Any, limiter_state.lock):
                        try:
                            current_next_allowed = object.__getattribute__(
                                limiter_state.target,
                                "_next_allowed",
                            )
                        except Exception:  # noqa: BLE001 - hostile limiter state
                            current_next_allowed = None
                        restored_next_allowed = limiter_state.next_allowed
                        if type(current_next_allowed) in {int, float}:
                            try:
                                numeric_next_allowed = float(current_next_allowed)
                            except (OverflowError, ValueError):
                                pass
                            else:
                                plausible_deadline = monotonic() + limiter_state.interval_seconds
                                if not (
                                    isfinite(numeric_next_allowed)
                                    and 0.0 <= numeric_next_allowed <= plausible_deadline
                                ):
                                    numeric_next_allowed = limiter_state.next_allowed
                                restored_next_allowed = max(
                                    restored_next_allowed,
                                    numeric_next_allowed,
                                )
                        restore_exact_type(limiter_state.target, limiter_state.target_type)
                        current_limiter_namespace = vars(limiter_state.target)
                        if current_limiter_namespace is not limiter_state.namespace:
                            object.__setattr__(
                                limiter_state.target,
                                "__dict__",
                                limiter_state.namespace,
                            )
                        limiter_state.namespace.clear()
                        limiter_state.namespace.update(
                            {
                                "interval_seconds": limiter_state.interval_seconds,
                                "_lock": limiter_state.lock,
                                "_next_allowed": restored_next_allowed,
                            }
                        )
            for frozen_state in expected.atlas_frozen_configurations:
                restore_exact_type(frozen_state.target, frozen_state.target_type)
                for name, value in frozen_state.attributes:
                    object.__setattr__(frozen_state.target, name, value)
            for track_state in expected.atlas_track_configurations:
                restore_exact_type(track_state.target, DeclaredReferenceTrackAdapter)
                restored_track = DeclaredReferenceTrackAdapter.from_dict(
                    track_state.canonical.to_dict()
                )
                for item in fields(restored_track):
                    object.__setattr__(
                        track_state.target,
                        item.name,
                        getattr(restored_track, item.name),
                    )
            for mapping_state in expected.atlas_nested_mappings:
                mapping_state.target.clear()
                mapping_state.target.update(dict(mapping_state.items))
            for retriever_state in (
                *expected.atlas_nested_instances,
                expected.reference_retriever_configuration,
                expected.atlas_retriever_configuration,
            ):
                if retriever_state is None:
                    continue
                restore_instance_namespace(retriever_state)
            for core_target, expected_core_type in (
                (expected.builder, HypothesisBuilder),
                (expected.builder_limits_object, HypothesisWorkLimits),
                (expected.planner, ExperimentPlanner),
                (expected.planner_limits_object, ExperimentPlanningLimits),
                (expected.validator, ContractValidator),
                (expected.validator_limits_object, ValidationLimits),
                (expected.policy, ResearchPolicy),
                (expected.policy_limits_object, PolicyLimits),
                (expected.release_gate, ReleaseGate),
                (expected.release_validator, ContractValidator),
                (expected.release_validator_limits_object, ValidationLimits),
                (expected.run_store.store, RunStore),
                (expected.run_store.object_store, ObjectStore),
            ):
                restore_exact_type(core_target, expected_core_type)
            self._restore_frozen_fields(
                expected.builder_limits_object,
                expected.builder_limits,
            )
            self._restore_frozen_fields(
                expected.planner_limits_object,
                expected.planner_limits,
            )
            self._restore_frozen_fields(
                expected.validator_limits_object,
                expected.validator_limits,
            )
            self._restore_frozen_fields(
                expected.policy_limits_object,
                expected.policy_limits,
            )
            self._restore_frozen_fields(
                expected.release_validator_limits_object,
                expected.release_validator_limits,
            )

            registry_state = expected.adapter_registry_configuration
            if registry_state is not None:
                restore_exact_type(registry_state.registry, AdapterRegistry)
                restore_exact_type(registry_state.limits_object, AdapterLimits)
                self._restore_frozen_fields(
                    registry_state.limits_object,
                    registry_state.limits,
                )
                with registry_state.lock:
                    for selected_entry in expected.selected_adapter_entries:
                        adapter_id = selected_entry.metadata.adapter_id
                        registry_state.entries[adapter_id] = RegistryEntry(
                            selected_entry.metadata,
                            selected_entry.adapter,
                            selected_entry.metadata_address,
                        )
                    vars(registry_state.registry).clear()
                    vars(registry_state.registry).update(
                        {
                            "_limits": registry_state.limits_object,
                            "_limits_address": registry_state.limits_address,
                            "_entries": registry_state.entries,
                            "_lock": registry_state.lock,
                        }
                    )

            vars(expected.builder).clear()
            vars(expected.builder)["limits"] = expected.builder_limits_object
            vars(expected.planner).clear()
            vars(expected.planner)["limits"] = expected.planner_limits_object
            vars(expected.validator).clear()
            vars(expected.validator)["limits"] = expected.validator_limits_object
            vars(expected.policy).clear()
            vars(expected.policy)["limits"] = expected.policy_limits_object
            vars(expected.release_validator).clear()
            vars(expected.release_validator)["limits"] = expected.release_validator_limits_object
            vars(expected.release_gate).clear()
            vars(expected.release_gate).update(
                {
                    "policy": expected.policy,
                    "validator": expected.release_validator,
                }
            )

            store = expected.run_store
            vars(store.object_store).clear()
            vars(store.object_store).update(
                {
                    "root": store.object_root,
                    "objects": store.objects,
                    "_locks": store.object_locks,
                    "_lock": store.object_lock,
                }
            )
            vars(store.store).clear()
            vars(store.store).update(
                {
                    "root": store.root,
                    "store": store.object_store,
                    "runs": store.runs,
                    "_locks": store.locks,
                    "_lock": store.run_lock,
                }
            )

            runtime_state.namespace.update(
                {
                    "builder": expected.builder,
                    "planner": expected.planner,
                    "validator": expected.validator,
                    "policy": expected.policy,
                    "release_gate": expected.release_gate,
                    "store": store.store,
                    "reference_retriever": expected.reference_retriever,
                    "atlas_retriever": expected.atlas_retriever,
                    "adapter_registry": expected.adapter_registry,
                    "_rna_input_max_bytes": expected.rna_input_max_bytes,
                    "_source_closure_max_bytes": expected.source_closure_max_bytes,
                    "_evaluation_lock": expected.evaluation_lock,
                    "_evaluation_active": expected.evaluation_active,
                }
            )
            assert_configuration(expected, guard_state)
        except Exception as exc:  # noqa: BLE001 - restoration is a fail-closed boundary
            raise error_type(  # type: ignore[operator]
                "runtime evaluation configuration could not be restored"
            ) from exc
        return changed

    def _link_atlas_claims(
        self,
        manifest: CaseManifest,
        bundles: tuple[AtlasBundle, ...],
        *,
        max_claims: int | None = None,
    ) -> tuple[tuple[EvidenceClaim, ...], tuple[str, ...]]:
        """Bind variant-scoped atlas observations once to the best eligible element edge."""

        if type(manifest) is not CaseManifest:
            raise ValidationError("atlas claim linking requires an exact CaseManifest")
        if type(bundles) is not tuple or any(type(bundle) is not AtlasBundle for bundle in bundles):
            raise ValidationError("atlas claim linking requires exact AtlasBundle values")
        if len(bundles) != len(manifest.variants):
            raise ValidationError("atlas bundles must cover every manifest variant exactly once")
        claim_ceiling = (
            self.builder.limits.max_external_claims if max_claims is None else max_claims
        )
        if type(claim_ceiling) is not int or claim_ceiling < 0:
            raise ValidationError("atlas claim ceiling must be a non-negative integer")
        claims: list[EvidenceClaim] = []
        warnings: list[str] = []
        for variant, bundle in zip(manifest.variants, bundles, strict=True):
            if bundle.variant_id != variant.variant_id:
                raise ValidationError("atlas bundle order does not match manifest variants")
            eligible = self.builder._eligible_elements(  # noqa: SLF001 - one runtime/builder seam
                variant,
                manifest.candidate_elements,
            )
            if not eligible:
                link_warning = self._atlas_link_warning(variant, eligible, bundle)
                if link_warning is not None:
                    warnings.append(link_warning)
                continue
            selected = min(
                eligible,
                key=lambda element: (
                    -element_relevance(variant, element)[0],
                    element.element_id,
                ),
            )
            edge_id = self.builder._edge_id(  # noqa: SLF001 - deterministic builder contract
                variant.variant_id,
                selected.element_id,
                EdgeType.VARIANT_TO_ELEMENT,
            )
            if len(bundle.observations) > claim_ceiling - len(claims):
                raise ValidationError(
                    f"external_claims exceeds the configured maximum of {claim_ceiling} items"
                )
            linked = bundle.to_evidence_claims(
                variant=variant,
                context=manifest.context,
                edge_id=edge_id,
            )
            if len(linked) != len(bundle.observations):
                raise ValidationError("atlas claim conversion is incomplete")
            claims.extend(linked)
            link_warning = self._atlas_link_warning(variant, eligible, bundle)
            if link_warning is not None:
                warnings.append(link_warning)
        return tuple(claims), tuple(warnings)

    @staticmethod
    def _atlas_link_warning(
        variant: VariantIdentity,
        eligible: tuple[CandidateElement, ...],
        bundle: AtlasBundle,
    ) -> str | None:
        if not bundle.observations:
            return None
        if not eligible:
            return (
                f"Atlas observations for {variant.variant_id} were retained in their "
                "source bundle but not promoted to claims because no eligible element "
                "edge exists."
            )
        if len(eligible) == 1:
            return None
        selected = min(
            eligible,
            key=lambda element: (
                -element_relevance(variant, element)[0],
                element.element_id,
            ),
        )
        return (
            f"Atlas observations for {variant.variant_id} were linked once to "
            f"highest-relevance element {selected.element_id}; {len(eligible) - 1} "
            "additional eligible element edge(s) were not duplicated."
        )

    def _retain_source_record(
        self,
        records: dict[str, Mapping[str, Any]],
        record: Mapping[str, Any],
        retained_bytes: int,
        *,
        label: str,
        record_ceiling: int | None = None,
        reserved_records: int = 0,
        object_max_bytes: int | None = None,
        source_closure_max_bytes: int | None = None,
    ) -> tuple[str, int]:
        """Address and charge one unique source object before later work is attempted."""

        if type(records) is not dict or type(record) is not dict:
            raise ValidationError(f"{label} source record must be an exact JSON object")
        if type(retained_bytes) is not int or retained_bytes < 0:
            raise ValidationError("source record closure byte accounting is invalid")
        object_ceiling = (
            self._persisted_object_max_bytes() if object_max_bytes is None else object_max_bytes
        )
        closure_ceiling = (
            self._source_closure_max_bytes
            if source_closure_max_bytes is None
            else source_closure_max_bytes
        )
        if type(object_ceiling) is not int or object_ceiling <= 0:
            raise ValidationError("persisted object byte ceiling is invalid")
        if type(closure_ceiling) is not int or closure_ceiling <= 0:
            raise ValidationError("source closure byte ceiling is invalid")
        try:
            encoded = canonical_bytes(record)
        except (OverflowError, RecursionError, TypeError, UnicodeError, ValueError) as exc:
            raise ValidationError(f"{label} source record is not canonical JSON") from exc
        address = f"sha256:{hashlib.sha256(encoded).hexdigest()}"
        existing = records.get(address)
        if existing is not None:
            if canonical_bytes(existing) != encoded:
                raise ValidationError(f"{label} source address collides with another source")
            return address, retained_bytes
        if record_ceiling is not None:
            self._require_source_record_capacity(
                records,
                record_ceiling=record_ceiling,
                reserved_records=reserved_records,
            )
        if len(encoded) > object_ceiling:
            raise ValidationError(
                f"{label} source record exceeds the persisted object byte ceiling"
            )
        if len(encoded) > closure_ceiling - retained_bytes:
            raise ValidationError(
                "source record closure exceeds its aggregate canonical byte ceiling"
            )
        records[address] = record
        return address, retained_bytes + len(encoded)

    @staticmethod
    def _require_source_record_capacity(
        records: dict[str, Mapping[str, Any]],
        *,
        record_ceiling: int,
        reserved_records: int,
        required_records: int = 1,
    ) -> None:
        if type(records) is not dict:
            raise ValidationError("source record closure accounting is invalid")
        if type(record_ceiling) is not int or record_ceiling <= 0:
            raise ValidationError("source record closure ceiling is invalid")
        if type(reserved_records) is not int or reserved_records < 0:
            raise ValidationError("reserved source record accounting is invalid")
        if type(required_records) is not int or required_records <= 0:
            raise ValidationError("required source record accounting is invalid")
        if len(records) + reserved_records + required_records > record_ceiling:
            raise ValidationError(
                f"source_bundle_addresses exceeds the configured maximum of {record_ceiling} items"
            )

    def _require_source_callback_capacity(
        self,
        retained_bytes: int,
        records: dict[str, Mapping[str, Any]],
        *,
        record_ceiling: int,
        reserved_records: int,
        required_records: int = 1,
        source_closure_max_bytes: int | None = None,
    ) -> None:
        """Reject an untrusted source stage once no closure capacity remains."""

        if type(retained_bytes) is not int or retained_bytes < 0:
            raise ValidationError("source record closure byte accounting is invalid")
        closure_ceiling = (
            self._source_closure_max_bytes
            if source_closure_max_bytes is None
            else source_closure_max_bytes
        )
        if type(closure_ceiling) is not int or closure_ceiling <= 0:
            raise ValidationError("source closure byte ceiling is invalid")
        if retained_bytes >= closure_ceiling:
            raise ValidationError(
                "source record closure exceeds its aggregate canonical byte ceiling"
            )
        self._require_source_record_capacity(
            records,
            record_ceiling=record_ceiling,
            reserved_records=reserved_records,
            required_records=required_records,
        )

    @staticmethod
    def _validate_event_payload_size(payload: Mapping[str, Any], label: str) -> None:
        try:
            payload_bytes = len(canonical_bytes(payload))
        except (OverflowError, RecursionError, TypeError, UnicodeError, ValueError) as exc:
            raise ValidationError(f"{label} event payload is not canonical JSON") from exc
        if payload_bytes > MAX_EVENT_PAYLOAD_BYTES:
            raise ValidationError(
                f"{label} event payload exceeds the maximum canonical size of "
                f"{MAX_EVENT_PAYLOAD_BYTES} bytes"
            )

    @staticmethod
    def _merge_adapter_elements(
        manifest: CaseManifest,
        resolution: AdapterResolutionReport,
    ) -> tuple[CandidateElement, ...]:
        """Return the exact candidate set produced by one adapter resolution."""

        if type(manifest) is not CaseManifest or type(resolution) is not AdapterResolutionReport:
            raise ValidationError("adapter materialization requires exact typed inputs")
        if resolution.manifest_address != manifest.content_address:
            raise ValidationError("adapter resolution does not belong to its base manifest")
        elements = {element.element_id: element for element in manifest.candidate_elements}
        for element in resolution.elements:
            existing = elements.get(element.element_id)
            if existing is not None and canonical_bytes(existing.to_dict()) != canonical_bytes(
                element.to_dict()
            ):
                raise ValidationError(
                    "adapter element conflicts with an existing manifest element: "
                    f"{element.element_id}"
                )
            elements[element.element_id] = element
        return tuple(elements[key] for key in sorted(elements))

    @classmethod
    def _materialize_adapter_manifest(
        cls,
        manifest: CaseManifest,
        resolution: AdapterResolutionReport,
        source_addresses: tuple[str, ...],
    ) -> CaseManifest:
        """Merge resolved elements and bind every adapter input into run identity."""

        elements = cls._merge_adapter_elements(manifest, resolution)
        if len(source_addresses) != len(_ADAPTER_INPUT_VERSION_KEYS):
            raise ValidationError("adapter materialization source closure is incomplete")
        additions = dict(zip(_ADAPTER_INPUT_VERSION_KEYS, source_addresses, strict=True))
        versions = dict(manifest.input_versions)
        for key, address in additions.items():
            if key in versions:
                raise ValidationError(f"manifest input_versions reserves adapter key: {key}")
            versions[key] = address
        return replace(
            manifest,
            candidate_elements=elements,
            input_versions=dict(sorted(versions.items())),
        )

    @staticmethod
    def _validate_reference_enrichment_transition(
        base_manifest: CaseManifest,
        effective_manifest: CaseManifest,
        source_elements: tuple[Any, ...],
    ) -> CaseManifest:
        """Allow live retrieval to add only bundle-backed candidates and versions."""

        if (
            type(base_manifest) is not CaseManifest
            or type(effective_manifest) is not CaseManifest
            or type(source_elements) is not tuple
            or any(type(element) is not CandidateElement for element in source_elements)
        ):
            raise ValidationError("reference enrichment transition requires exact typed inputs")
        base = CaseManifest.from_dict(base_manifest.to_dict())
        effective = CaseManifest.from_dict(effective_manifest.to_dict())
        immutable_base = (
            base.case_id,
            base.subject_id,
            base.context,
            base.variants,
            base.metadata,
            base.requested_by,
        )
        immutable_effective = (
            effective.case_id,
            effective.subject_id,
            effective.context,
            effective.variants,
            effective.metadata,
            effective.requested_by,
        )
        if canonical_bytes(immutable_base) != canonical_bytes(immutable_effective):
            raise ValidationError("reference enrichment changed immutable manifest identity")
        if any(
            effective.input_versions.get(key) != value for key, value in base.input_versions.items()
        ):
            raise ValidationError("reference enrichment changed existing input versions")

        effective_elements = {
            element.element_id: canonical_bytes(element.to_dict())
            for element in effective.candidate_elements
        }
        base_elements = {
            element.element_id: canonical_bytes(element.to_dict())
            for element in base.candidate_elements
        }
        if any(
            effective_elements.get(element_id) != encoded
            for element_id, encoded in base_elements.items()
        ):
            raise ValidationError("reference enrichment changed or removed a base element")
        bundle_elements: dict[str, bytes] = {}
        for element in source_elements:
            encoded = canonical_bytes(element.to_dict())
            previous = bundle_elements.setdefault(element.element_id, encoded)
            if previous != encoded:
                raise ValidationError("reference enrichment bundles conflict on element identity")
        for element_id, encoded in effective_elements.items():
            if element_id not in base_elements and bundle_elements.get(element_id) != encoded:
                raise ValidationError(
                    "reference enrichment added an element absent from its source bundles"
                )
        if any(
            effective_elements.get(element_id) != encoded
            for element_id, encoded in bundle_elements.items()
        ):
            raise ValidationError("reference enrichment omitted or changed a source bundle element")
        return effective

    def evaluate(
        self,
        manifest: CaseManifest,
        *,
        live_reference: bool = False,
        rna_consequences: Iterable[RNAConsequenceEvidence] = (),
        adapter_ids: tuple[str, ...] = (),
    ) -> Dossier:
        """Evaluate a manifest and persist its immutable output."""

        coordinator = runtime_callback_scope
        if coordinator is not _callback_isolation_module.runtime_callback_scope:
            raise ValidationError("runtime callback isolation scope is invalid")
        active_evaluation_runtime_ids = _ACTIVE_EVALUATION_RUNTIME_IDS
        with coordinator():
            active_runtime_ids = active_evaluation_runtime_ids.get()
            if active_runtime_ids:
                raise ValidationError("recursive runtime evaluation is not supported")
            if type(live_reference) is not bool:
                raise ValidationError("live_reference must be an exact boolean")
            if type(adapter_ids) is not tuple or any(type(item) is not str for item in adapter_ids):
                raise ValidationError("adapter_ids must be an exact tuple of strings")
            if type(self) is not CaseRuntime:
                raise ValidationError("runtime must be an exact CaseRuntime")
            runtime_namespace = object.__getattribute__(self, "__dict__")
            if (
                type(runtime_namespace) is not dict
                or frozenset(runtime_namespace) != _RUNTIME_INSTANCE_FIELDS
            ):
                raise ValidationError("runtime has non-canonical instance state")
            evaluation_lock = runtime_namespace["_evaluation_lock"]
            if type(evaluation_lock) is not _RLOCK_TYPE:
                raise ValidationError("runtime evaluation lock is invalid")
            with evaluation_lock:
                runtime_identity = id(self)
                evaluation_active = runtime_namespace["_evaluation_active"]
                if type(evaluation_active) is not bool:
                    raise ValidationError("runtime evaluation state is invalid")
                if evaluation_active:
                    raise ValidationError("recursive runtime evaluation is not supported")

                guard_detacher = detached_callback_guard

                def detached_bound_method(bound_method: object) -> Any:
                    if (
                        type(bound_method) is not MethodType
                        or type(bound_method.__func__) is not FunctionType
                    ):
                        raise ValidationError("runtime evaluation guard methods are invalid")
                    function = bound_method.__func__
                    clone = guard_detacher(function)
                    return MethodType(clone, self)

                capture_evaluation_configuration = self._capture_evaluation_configuration
                evaluation_guard_state = self._evaluation_guard_state
                assert_evaluation_configuration = detached_bound_method(
                    self._assert_evaluation_configuration
                )
                restore_evaluation_configuration = detached_bound_method(
                    self._restore_evaluation_configuration
                )
                evaluate_once = self._evaluate_once
                evaluation_error_type = ValidationError
                evaluation_base_exception_type = BaseException
                restoration_exception_type = Exception
                activity_token = active_evaluation_runtime_ids.set(
                    active_runtime_ids | {runtime_identity}
                )
                runtime_namespace["_evaluation_active"] = True
                try:
                    configuration = capture_evaluation_configuration()
                    guard_state = evaluation_guard_state(configuration)
                    try:
                        if adapter_ids:
                            registry = configuration.adapter_registry
                            if registry is None:
                                raise ValidationError(
                                    "adapter_ids require a configured AdapterRegistry"
                                )
                            selected_adapter_snapshot, selected_adapter_entries = (
                                AdapterRegistry.selected_entries(
                                    registry,
                                    adapter_ids,
                                )
                            )
                            configuration = replace(
                                configuration,
                                selected_adapter_ids=adapter_ids,
                                selected_adapter_snapshot=selected_adapter_snapshot,
                                selected_adapter_entries=selected_adapter_entries,
                            )
                            assert_evaluation_configuration(configuration, guard_state)
                        result = evaluate_once(
                            manifest,
                            live_reference=live_reference,
                            rna_consequences=rna_consequences,
                            adapter_ids=adapter_ids,
                            configuration=configuration,
                            guard_state=guard_state,
                            assert_evaluation_configuration=assert_evaluation_configuration,
                        )
                    except evaluation_base_exception_type:
                        try:
                            restore_evaluation_configuration(
                                configuration,
                                guard_state,
                                assert_evaluation_configuration,
                            )
                        except restoration_exception_type as restore_exc:
                            raise evaluation_error_type(
                                "runtime evaluation configuration could not be restored"
                            ) from restore_exc
                        raise
                    if restore_evaluation_configuration(
                        configuration,
                        guard_state,
                        assert_evaluation_configuration,
                    ):
                        raise evaluation_error_type(
                            "runtime evaluation configuration changed during untrusted work"
                        )
                    return result
                finally:
                    runtime_namespace["_evaluation_active"] = False
                    active_evaluation_runtime_ids.reset(activity_token)

    def _evaluate_once(
        self,
        manifest: CaseManifest,
        *,
        live_reference: bool,
        rna_consequences: Iterable[RNAConsequenceEvidence],
        adapter_ids: tuple[str, ...],
        configuration: _EvaluationConfigurationSnapshot,
        guard_state: _EvaluationGuardState,
        assert_evaluation_configuration: Any,
    ) -> Dossier:
        """Run one evaluation under a captured, externally guarded configuration."""

        assert_evaluation_configuration(configuration, guard_state)
        builder = configuration.builder
        builder_limits = configuration.builder_limits
        planner = configuration.planner
        validator_limits = configuration.validator_limits
        external_claim_max = min(
            builder_limits.max_external_claims,
            validator_limits.max_evidence_claims,
        )
        source_receipt_max = min(
            validator_limits.max_source_receipts,
            validator_limits.max_sequence_items,
        )
        persisted_object_max_bytes = validator_limits.max_canonical_bytes
        rna_input_max_bytes = configuration.rna_input_max_bytes
        rna_object_max_bytes = min(rna_input_max_bytes, persisted_object_max_bytes)
        source_closure_max_bytes = configuration.source_closure_max_bytes
        configured_reference_retriever = configuration.reference_retriever
        if live_reference and configured_reference_retriever is None:
            configured_reference_retriever = PublicReferenceRetriever(
                cache_root=configuration.run_store.root / "source-cache"
            )
        configured_atlas_retriever = configuration.atlas_retriever
        configured_adapter_registry = configuration.adapter_registry
        if adapter_ids and (
            configured_adapter_registry is None or configuration.selected_adapter_snapshot is None
        ):
            raise ValidationError("adapter_ids require a captured AdapterRegistry selection")
        reserved_adapter_ids = tuple(
            sorted(set(adapter_ids).intersection(_RESERVED_NATIVE_EVIDENCE_PRODUCERS))
        )
        if reserved_adapter_ids:
            raise ValidationError(
                "adapter IDs collide with reserved evidence producers: "
                f"{list(reserved_adapter_ids)}"
            )
        self._validate_manifest_contract(manifest, "case manifest")
        self._reject_reserved_adapter_versions(manifest, "case manifest")
        manifest = CaseManifest.from_dict(manifest.to_dict())
        builder.validate_inputs(manifest, rna_consequences=())
        if isinstance(rna_consequences, (str, bytes, bytearray, Mapping)):
            raise ValidationError("rna_consequences must be an iterable of RNA consequences")
        try:
            rna_iterator = iter(rna_consequences)
        except TypeError as exc:
            raise ValidationError("rna_consequences must be iterable") from exc
        detached_rna_rows: list[RNAConsequenceEvidence] = []
        rna_batch_empty = {
            "schema_version": "1.0.0",
            "kind": "rna_consequence_batch",
            "consequences": [],
        }
        rna_batch_bytes = len(canonical_bytes(rna_batch_empty))
        while True:
            try:
                row = next(rna_iterator)
            except StopIteration:
                break
            if len(detached_rna_rows) >= builder_limits.max_rna_consequences:
                raise ValidationError(
                    "rna_consequences exceeds the configured maximum of "
                    f"{builder_limits.max_rna_consequences} items"
                )
            validate_rna_consequence(row)
            raw_row, encoded_row = self._preflight_rna_input_row(
                row.to_dict(),
                index=len(detached_rna_rows),
            )
            prospective_batch_bytes = (
                rna_batch_bytes + len(encoded_row) + (1 if detached_rna_rows else 0)
            )
            if prospective_batch_bytes > rna_object_max_bytes:
                raise ValidationError(
                    "RNA input exceeds the configured persisted byte ceiling of "
                    f"{rna_object_max_bytes}"
                )
            if prospective_batch_bytes > source_closure_max_bytes:
                raise ValidationError(
                    "source record closure exceeds its aggregate canonical byte ceiling"
                )
            detached_rna_rows.append(RNAConsequenceEvidence.from_mapping(raw_row))
            rna_batch_bytes = prospective_batch_bytes
        rna_rows = tuple(detached_rna_rows)
        assert_evaluation_configuration(configuration, guard_state)
        self._enforce_policy_texts((manifest.case_id, manifest.requested_by), "manifest")
        submitted_input_address = manifest.content_address
        build_manifest = manifest
        source_records: dict[str, Mapping[str, Any]] = {}
        source_receipts: tuple[Mapping[str, Any], ...] = ()
        source_bundle_addresses: tuple[str, ...] = ()
        reference_bundle_addresses: tuple[str, ...] = ()
        reference_effective_input_address: str | None = None
        reference_receipt_count = 0
        reference_event_payload: dict[str, Any] | None = None
        atlas_replay_input_addresses: tuple[str, ...] = ()
        atlas_bundle_addresses: tuple[str, ...] = ()
        atlas_event_warnings: tuple[str, ...] = ()
        runtime_warnings: tuple[str, ...] = ()
        atlas_claims: tuple[EvidenceClaim, ...] = ()
        adapter_claims: tuple[EvidenceClaim, ...] = ()
        adapter_resolution: AdapterResolutionReport | None = None
        adapter_claim_report: AdapterClaimCollectionReport | None = None
        adapter_source_addresses: tuple[str, ...] = ()
        enrichment: EnrichmentResult | None = None
        source_closure_bytes = 0
        reserved_source_records = 0
        rna_input: dict[str, Any] | None = None
        rna_input_address: str | None = None
        if rna_rows:
            rna_input = {
                "schema_version": "1.0.0",
                "kind": "rna_consequence_batch",
                "consequences": [
                    item.to_dict() for item in sorted(rna_rows, key=lambda row: row.content_address)
                ],
            }
            self._preflight_rna_input_rows(
                rna_input["consequences"],
                expected_count=len(rna_rows),
            )
            encoded_rna_input = canonical_bytes(rna_input)
            if len(encoded_rna_input) != rna_batch_bytes:
                raise ValidationError("RNA input byte accounting is inconsistent")
            source_closure_bytes = len(encoded_rna_input)
            rna_input_address = f"sha256:{hashlib.sha256(encoded_rna_input).hexdigest()}"
            reserved_source_records = 1
        if live_reference:
            submitted_record = manifest.to_dict()
            retained_submitted_address, source_closure_bytes = self._retain_source_record(
                source_records,
                submitted_record,
                source_closure_bytes,
                label="submitted manifest",
                record_ceiling=validator_limits.max_source_bundles,
                reserved_records=reserved_source_records,
                object_max_bytes=persisted_object_max_bytes,
                source_closure_max_bytes=source_closure_max_bytes,
            )
            if retained_submitted_address != submitted_input_address:
                raise ValidationError("submitted manifest address changed during preparation")
            self._require_source_callback_capacity(
                source_closure_bytes,
                source_records,
                record_ceiling=validator_limits.max_source_bundles,
                reserved_records=reserved_source_records,
                source_closure_max_bytes=source_closure_max_bytes,
            )
            self._require_source_record_capacity(
                source_records,
                record_ceiling=validator_limits.max_source_bundles,
                reserved_records=reserved_source_records,
                required_records=len(manifest.variants),
            )
            retriever = configured_reference_retriever
            if retriever is None:  # pragma: no cover - resolved before untrusted work
                raise ValidationError("live reference retriever preparation is incomplete")
            retrieval_manifest = CaseManifest.from_dict(manifest.to_dict())
            retrieval_input_bytes = canonical_bytes(retrieval_manifest.to_dict())
            enrichment = retriever.enrich_manifest(retrieval_manifest)
            assert_evaluation_configuration(configuration, guard_state)
            if type(enrichment) is not EnrichmentResult:
                raise ValidationError("reference retriever returned an invalid enrichment result")
            try:
                current_input_bytes = canonical_bytes(retrieval_manifest.to_dict())
            except (TypeError, ValueError, OverflowError, UnicodeError, RecursionError) as exc:
                raise ValidationError("reference retriever mutated its manifest input") from exc
            if current_input_bytes != retrieval_input_bytes:
                raise ValidationError("reference retriever mutated its manifest input")
            if type(enrichment.manifest) is not CaseManifest:
                raise ValidationError("reference retriever returned an invalid enrichment manifest")
            try:
                returned_variants = enrichment.manifest.variants
                returned_elements = enrichment.manifest.candidate_elements
            except Exception as exc:  # noqa: BLE001 - forged exact callback result
                raise ValidationError(
                    "reference retriever returned an invalid enrichment manifest"
                ) from exc
            if type(returned_variants) is not tuple or type(returned_elements) is not tuple:
                raise ValidationError("reference retriever returned an invalid enrichment manifest")
            if (
                len(returned_variants) > validator_limits.max_variants
                or len(returned_elements) > validator_limits.max_elements
            ):
                raise ValidationError(
                    "reference retriever returned an enrichment manifest outside work limits"
                )
            try:
                detached_enrichment_manifest = CaseManifest.from_dict(enrichment.manifest.to_dict())
            except Exception as exc:  # noqa: BLE001 - forged exact callback result
                raise ValidationError(
                    "reference retriever returned an invalid enrichment manifest"
                ) from exc
            if type(enrichment.bundles) is not tuple:
                raise ValidationError("reference retriever returned invalid enrichment bundles")
            if (
                len(enrichment.bundles) != len(detached_enrichment_manifest.variants)
                or len(enrichment.bundles) > MAX_REFERENCE_VARIANTS
            ):
                raise ValidationError(
                    "reference retriever returned an invalid enrichment bundle count"
                )
            if (
                type(enrichment.warnings) is not tuple
                or len(enrichment.warnings) > MAX_REFERENCE_WARNINGS
                or any(type(warning) is not str for warning in enrichment.warnings)
            ):
                raise ValidationError("reference retriever returned invalid enrichment warnings")
            aggregate_elements = 0
            aggregate_raw_features = 0
            aggregate_receipts = 0
            aggregate_bundle_warnings = 0
            for bundle in enrichment.bundles:
                if type(bundle) is not ReferenceBundle:
                    raise ValidationError(
                        "reference retriever returned an invalid reference bundle"
                    )
                try:
                    bundle_elements = bundle.elements
                    bundle_raw_features = bundle.raw_features
                    bundle_receipts = bundle.receipts
                    bundle_warnings = bundle.warnings
                except Exception as exc:  # noqa: BLE001 - forged exact callback result
                    raise ValidationError(
                        "reference retriever returned an invalid reference bundle"
                    ) from exc
                if (
                    type(bundle_elements) is not tuple
                    or type(bundle_raw_features) is not tuple
                    or type(bundle_receipts) is not tuple
                    or type(bundle_warnings) is not tuple
                ):
                    raise ValidationError(
                        "reference retriever returned an invalid reference bundle"
                    )
                if (
                    len(bundle_elements) > MAX_REFERENCE_FEATURES
                    or len(bundle_raw_features) > MAX_REFERENCE_FEATURES
                    or len(bundle_receipts) > MAX_REFERENCE_RECEIPTS
                    or len(bundle_warnings) > MAX_REFERENCE_WARNINGS
                ):
                    raise ValidationError(
                        "reference retriever returned a reference bundle outside work limits"
                    )
                aggregate_elements += len(bundle_elements)
                aggregate_raw_features += len(bundle_raw_features)
                aggregate_receipts += len(bundle_receipts)
                aggregate_bundle_warnings += len(bundle_warnings)
                if (
                    aggregate_elements > MAX_ENRICHED_ELEMENTS
                    or aggregate_raw_features > MAX_ENRICHED_ELEMENTS
                    or aggregate_receipts > MAX_REFERENCE_VARIANTS * MAX_REFERENCE_RECEIPTS
                    or aggregate_bundle_warnings > MAX_REFERENCE_WARNINGS
                ):
                    raise ValidationError(
                        "reference retriever returned enrichment bundles outside work limits"
                    )
            detached_reference_bundles: list[ReferenceBundle] = []
            retained_reference_addresses: list[str] = []
            for bundle in enrichment.bundles:
                try:
                    record = bundle.to_dict()
                except Exception as exc:  # noqa: BLE001 - forged exact callback result
                    raise ValidationError(
                        "reference retriever returned an invalid reference bundle"
                    ) from exc
                address, source_closure_bytes = self._retain_source_record(
                    source_records,
                    record,
                    source_closure_bytes,
                    label="reference bundle",
                    record_ceiling=validator_limits.max_source_bundles,
                    reserved_records=reserved_source_records,
                    object_max_bytes=persisted_object_max_bytes,
                    source_closure_max_bytes=source_closure_max_bytes,
                )
                try:
                    detached_reference_bundles.append(
                        ReferenceBundle.from_dict(
                            record,
                            detached_enrichment_manifest.context,
                        )
                    )
                except ValidationError:
                    raise
                except Exception as exc:  # noqa: BLE001 - forged exact callback result
                    raise ValidationError(
                        "reference retriever returned an invalid reference bundle"
                    ) from exc
                retained_reference_addresses.append(address)
            enrichment = EnrichmentResult(
                detached_enrichment_manifest,
                tuple(detached_reference_bundles),
                tuple(enrichment.warnings),
            )
            build_manifest = self._validate_reference_enrichment_transition(
                manifest,
                enrichment.manifest,
                tuple(element for bundle in enrichment.bundles for element in bundle.elements),
            )
            reference_effective_input_address = build_manifest.content_address
            self._validate_manifest_contract(build_manifest, "enriched case manifest")
            self._reject_reserved_adapter_versions(build_manifest, "enriched case manifest")
            builder.validate_inputs(
                build_manifest,
                rna_consequences=rna_rows,
            )
            reference_bundle_addresses = tuple(retained_reference_addresses)
            source_receipts = tuple(
                receipt.to_dict() for bundle in enrichment.bundles for receipt in bundle.receipts
            )
            reference_receipt_count = len(source_receipts)
            if reference_receipt_count > source_receipt_max:
                raise ValidationError(
                    f"source_receipts exceeds the configured maximum of {source_receipt_max} items"
                )
            source_receipt_count = reference_receipt_count
            runtime_warnings = enrichment.warnings
            if len(runtime_warnings) > validator_limits.max_sequence_items:
                raise ValidationError(
                    "warnings exceeds the configured maximum of "
                    f"{validator_limits.max_sequence_items} items"
                )
            reference_event_payload = {
                "submitted_input_address": submitted_input_address,
                "effective_input_address": reference_effective_input_address,
                "bundle_addresses": list(reference_bundle_addresses),
                "receipt_count": reference_receipt_count,
                "warnings": list(enrichment.warnings),
            }
            self._validate_event_payload_size(
                reference_event_payload,
                "public reference",
            )
            if configured_atlas_retriever is not None or isinstance(
                retriever, PublicReferenceRetriever
            ):
                atlas_retriever = (
                    PublicAtlasRetriever(retriever)
                    if configured_atlas_retriever is None
                    else configured_atlas_retriever
                )
                reference_by_variant = {bundle.variant_id: bundle for bundle in enrichment.bundles}
                detached_atlas_bundles: list[AtlasBundle] = []
                retained_atlas_replay_addresses: list[str] = []
                retained_atlas_addresses: list[str] = []
                atlas_claim_observation_count = 0
                atlas_warning_values: list[str] = []
                atlas_warning_seen: set[str] = set()
                projected_link_warnings: list[str] = []
                atlas_event_warning_seen: set[str] = set()
                runtime_warning_seen = set(runtime_warnings)
                atlas_warning_item_bytes = 0
                atlas_address_item_bytes = 0
                budget_probe = builder.build(
                    build_manifest,
                    self._run_id(build_manifest, rna_rows),
                    rna_consequences=rna_rows,
                    retained_owner_address=rna_input_address,
                )
                native_claim_count = len(budget_probe.claims)
                if native_claim_count > validator_limits.max_evidence_claims:
                    raise ValidationError(
                        "native evidence claims exceed the configured maximum of "
                        f"{validator_limits.max_evidence_claims} items"
                    )
                native_edge_claim_counts: dict[str, int] = {}
                for claim in budget_probe.claims:
                    native_edge_claim_counts[claim.edge_id] = (
                        native_edge_claim_counts.get(claim.edge_id, 0) + 1
                    )
                if any(
                    count > validator_limits.max_claims_per_edge
                    for count in native_edge_claim_counts.values()
                ):
                    raise ValidationError(
                        "native evidence claims exceed the configured per-edge maximum of "
                        f"{validator_limits.max_claims_per_edge} items"
                    )
                atlas_external_claim_max = min(
                    external_claim_max,
                    validator_limits.max_evidence_claims - native_claim_count,
                )
                atlas_edge_claim_counts: dict[str, int] = {}
                for variant in build_manifest.variants:
                    eligible_atlas_elements = builder._eligible_elements(  # noqa: SLF001
                        variant,
                        build_manifest.candidate_elements,
                    )
                    atlas_edge_id: str | None = None
                    atlas_edge_claim_max = 0
                    if eligible_atlas_elements:
                        selected_atlas_element = min(
                            eligible_atlas_elements,
                            key=lambda element: (
                                -element_relevance(variant, element)[0],
                                element.element_id,
                            ),
                        )
                        atlas_edge_id = builder._edge_id(  # noqa: SLF001
                            variant.variant_id,
                            selected_atlas_element.element_id,
                            EdgeType.VARIANT_TO_ELEMENT,
                        )
                        atlas_edge_claim_max = (
                            validator_limits.max_claims_per_edge
                            - native_edge_claim_counts.get(atlas_edge_id, 0)
                        )
                    if (
                        eligible_atlas_elements
                        and atlas_claim_observation_count >= atlas_external_claim_max
                    ):
                        raise ValidationError(
                            "external_claims exceeds the configured maximum of "
                            f"{atlas_external_claim_max} items"
                        )
                    if (
                        atlas_edge_id is not None
                        and atlas_edge_claim_counts.get(atlas_edge_id, 0) >= atlas_edge_claim_max
                    ):
                        raise ValidationError(
                            "external_claims exceeds the configured per-edge maximum of "
                            f"{validator_limits.max_claims_per_edge} items"
                        )
                    if source_receipt_count >= source_receipt_max:
                        raise ValidationError(
                            "source_receipts exceeds the configured maximum of "
                            f"{source_receipt_max} items"
                        )
                    if len(runtime_warning_seen) >= validator_limits.max_sequence_items:
                        raise ValidationError(
                            "warnings exceeds the configured maximum of "
                            f"{validator_limits.max_sequence_items} items"
                        )
                    minimum_address_count = len(retained_atlas_addresses) + 1
                    minimum_event_bytes = (
                        _ATLAS_EVENT_EMPTY_PAYLOAD_BYTES
                        + atlas_address_item_bytes
                        + (2 * _ATLAS_EVENT_ADDRESS_ITEM_BYTES)
                        + (2 * max(0, minimum_address_count - 1))
                        + atlas_warning_item_bytes
                        + max(0, len(atlas_event_warning_seen) - 1)
                        + len(str(atlas_claim_observation_count))
                        - 1
                    )
                    if minimum_event_bytes > MAX_EVENT_PAYLOAD_BYTES:
                        raise ValidationError(
                            "public atlas event payload exceeds the maximum canonical size of "
                            f"{MAX_EVENT_PAYLOAD_BYTES} bytes"
                        )
                    self._require_source_callback_capacity(
                        source_closure_bytes,
                        source_records,
                        record_ceiling=validator_limits.max_source_bundles,
                        reserved_records=reserved_source_records,
                        required_records=2,
                        source_closure_max_bytes=source_closure_max_bytes,
                    )
                    callback_variant = VariantIdentity.from_dict(variant.to_dict())
                    callback_context = ReferenceContext.from_dict(build_manifest.context.to_dict())
                    variant_input_bytes = canonical_bytes(callback_variant.to_dict())
                    context_input_bytes = canonical_bytes(callback_context.to_dict())
                    callback_query: AtlasQuery | None = None
                    callback_reference_bundle: ReferenceBundle | None = None
                    query_input_bytes: bytes | None = None
                    reference_input_bytes: bytes | None = None
                    if isinstance(atlas_retriever, PublicAtlasRetriever):
                        callback_query = AtlasQuery(
                            variant_id=callback_variant.variant_id,
                            window_bp=getattr(retriever, "window_bp", 2_000),
                        )
                        callback_reference_bundle = ReferenceBundle.from_dict(
                            reference_by_variant[callback_variant.variant_id].to_dict(),
                            callback_context,
                        )
                        query_input_bytes = canonical_bytes(callback_query.to_dict())
                        reference_input_bytes = canonical_bytes(callback_reference_bundle.to_dict())
                        returned_bundle = atlas_retriever.retrieve(
                            callback_variant,
                            callback_context,
                            query=callback_query,
                            reference_bundle=callback_reference_bundle,
                        )
                    else:
                        returned_bundle = atlas_retriever.retrieve(
                            callback_variant,
                            callback_context,
                        )
                    assert_evaluation_configuration(configuration, guard_state)
                    try:
                        current_variant_bytes = canonical_bytes(callback_variant.to_dict())
                        current_context_bytes = canonical_bytes(callback_context.to_dict())
                        current_query_bytes = (
                            None
                            if callback_query is None
                            else canonical_bytes(callback_query.to_dict())
                        )
                        current_reference_bytes = (
                            None
                            if callback_reference_bundle is None
                            else canonical_bytes(callback_reference_bundle.to_dict())
                        )
                    except Exception as exc:  # noqa: BLE001 - untrusted callback mutation
                        raise ValidationError(
                            "atlas retriever mutated its callback inputs"
                        ) from exc
                    if (
                        current_variant_bytes != variant_input_bytes
                        or current_context_bytes != context_input_bytes
                        or current_query_bytes != query_input_bytes
                        or current_reference_bytes != reference_input_bytes
                    ):
                        raise ValidationError("atlas retriever mutated its callback inputs")
                    if type(returned_bundle) is not AtlasBundle:
                        raise ValidationError("atlas retriever returned an invalid atlas bundle")
                    try:
                        returned_observations = returned_bundle.observations
                        returned_receipts = returned_bundle.receipts
                        returned_warnings = returned_bundle.warnings
                        returned_track_reports = returned_bundle.track_reports
                    except Exception as exc:  # noqa: BLE001 - forged exact callback result
                        raise ValidationError(
                            "atlas retriever returned an invalid atlas bundle"
                        ) from exc
                    if (
                        type(returned_observations) is not tuple
                        or type(returned_receipts) is not tuple
                        or type(returned_warnings) is not tuple
                        or type(returned_track_reports) is not tuple
                        or len(returned_observations) > 25_000
                        or len(returned_receipts) > 256
                        or len(returned_warnings) > 4_096
                        or len(returned_track_reports) > 256
                    ):
                        raise ValidationError(
                            "atlas retriever returned an atlas bundle outside work limits"
                        )
                    if eligible_atlas_elements and len(returned_observations) > (
                        atlas_external_claim_max - atlas_claim_observation_count
                    ):
                        raise ValidationError(
                            "external_claims exceeds the configured maximum of "
                            f"{atlas_external_claim_max} items"
                        )
                    if atlas_edge_id is not None and len(
                        returned_observations
                    ) > atlas_edge_claim_max - atlas_edge_claim_counts.get(atlas_edge_id, 0):
                        raise ValidationError(
                            "external_claims exceeds the configured per-edge maximum of "
                            f"{validator_limits.max_claims_per_edge} items"
                        )
                    returned_receipt_count = len(returned_receipts)
                    if returned_receipt_count > (source_receipt_max - source_receipt_count):
                        raise ValidationError(
                            "source_receipts exceeds the configured maximum of "
                            f"{source_receipt_max} items"
                        )
                    try:
                        returned_replay_inputs = returned_bundle.replay_inputs
                        if type(returned_replay_inputs) is not AtlasReplayInputs:
                            raise ValidationError(
                                "atlas retriever returned invalid atlas replay inputs"
                            )
                        reference_bundle = reference_by_variant[callback_variant.variant_id]
                        replay_record = returned_replay_inputs.to_dict()
                        detached_replay_inputs = AtlasReplayInputs.from_dict(
                            replay_record,
                            callback_variant,
                            callback_context,
                            reference_bundle=reference_bundle,
                        )
                        atlas_record = returned_bundle.to_dict()
                        detached_bundle = AtlasBundle.from_dict(
                            atlas_record,
                            callback_variant,
                            callback_context,
                            reference_bundle=reference_bundle,
                            replay_inputs=detached_replay_inputs,
                        )
                    except ValidationError:
                        raise
                    except Exception as exc:  # noqa: BLE001 - forged exact callback result
                        raise ValidationError(
                            "atlas retriever returned an invalid atlas bundle"
                        ) from exc
                    if (
                        len(detached_bundle.observations) != len(returned_observations)
                        or len(detached_bundle.receipts) != returned_receipt_count
                    ):
                        raise ValidationError(
                            "atlas retriever returned inconsistent atlas bundle collections"
                        )
                    replay_input_address, source_closure_bytes = self._retain_source_record(
                        source_records,
                        replay_record,
                        source_closure_bytes,
                        label="atlas replay inputs",
                        record_ceiling=validator_limits.max_source_bundles,
                        reserved_records=reserved_source_records,
                        object_max_bytes=persisted_object_max_bytes,
                        source_closure_max_bytes=source_closure_max_bytes,
                    )
                    atlas_address, source_closure_bytes = self._retain_source_record(
                        source_records,
                        atlas_record,
                        source_closure_bytes,
                        label="atlas bundle",
                        record_ceiling=validator_limits.max_source_bundles,
                        reserved_records=reserved_source_records,
                        object_max_bytes=persisted_object_max_bytes,
                        source_closure_max_bytes=source_closure_max_bytes,
                    )
                    if (
                        detached_replay_inputs.reference_bundle_address
                        != reference_bundle.content_address
                        or detached_bundle.source_bundle_address
                        != reference_bundle.content_address
                        or detached_bundle.replay_inputs_address
                        != detached_replay_inputs.content_address
                    ):
                        raise ValidationError(
                            "atlas replay-input/bundle pair does not bind its exact source closure"
                        )
                    if len(detached_bundle.receipts) > (source_receipt_max - source_receipt_count):
                        raise ValidationError(
                            "source_receipts exceeds the configured maximum of "
                            f"{source_receipt_max} items"
                        )
                    source_receipt_count += len(detached_bundle.receipts)
                    if eligible_atlas_elements:
                        if len(detached_bundle.observations) > (
                            atlas_external_claim_max - atlas_claim_observation_count
                        ):
                            raise ValidationError(
                                "external_claims exceeds the configured maximum of "
                                f"{atlas_external_claim_max} items"
                            )
                        atlas_claim_observation_count += len(detached_bundle.observations)
                        if atlas_edge_id is None:  # pragma: no cover - paired eligibility
                            raise ValidationError("atlas evidence edge accounting is incomplete")
                        atlas_edge_claim_counts[atlas_edge_id] = atlas_edge_claim_counts.get(
                            atlas_edge_id, 0
                        ) + len(detached_bundle.observations)
                    for warning in detached_bundle.warnings:
                        if warning not in runtime_warning_seen:
                            runtime_warning_seen.add(warning)
                            if len(runtime_warning_seen) > validator_limits.max_sequence_items:
                                raise ValidationError(
                                    "warnings exceeds the configured maximum of "
                                    f"{validator_limits.max_sequence_items} items"
                                )
                        if warning not in atlas_warning_seen:
                            atlas_warning_seen.add(warning)
                            atlas_warning_values.append(warning)
                        if warning not in atlas_event_warning_seen:
                            atlas_event_warning_seen.add(warning)
                            atlas_warning_item_bytes += len(canonical_bytes(warning))
                    projected_link_warning = self._atlas_link_warning(
                        variant,
                        eligible_atlas_elements,
                        detached_bundle,
                    )
                    if projected_link_warning is not None:
                        projected_link_warnings.append(projected_link_warning)
                        if projected_link_warning not in runtime_warning_seen:
                            runtime_warning_seen.add(projected_link_warning)
                            if len(runtime_warning_seen) > validator_limits.max_sequence_items:
                                raise ValidationError(
                                    "warnings exceeds the configured maximum of "
                                    f"{validator_limits.max_sequence_items} items"
                                )
                        if projected_link_warning not in atlas_event_warning_seen:
                            atlas_event_warning_seen.add(projected_link_warning)
                            atlas_warning_item_bytes += len(canonical_bytes(projected_link_warning))
                    atlas_address_item_bytes += len(canonical_bytes(replay_input_address))
                    atlas_address_item_bytes += len(canonical_bytes(atlas_address))
                    prospective_address_count = len(retained_atlas_addresses) + 1
                    prospective_warning_count = len(atlas_event_warning_seen)
                    prospective_event_bytes = (
                        _ATLAS_EVENT_EMPTY_PAYLOAD_BYTES
                        + atlas_address_item_bytes
                        + (2 * max(0, prospective_address_count - 1))
                        + atlas_warning_item_bytes
                        + max(0, prospective_warning_count - 1)
                        + len(str(atlas_claim_observation_count))
                        - 1
                    )
                    if prospective_event_bytes > MAX_EVENT_PAYLOAD_BYTES:
                        raise ValidationError(
                            "public atlas event payload exceeds the maximum canonical size of "
                            f"{MAX_EVENT_PAYLOAD_BYTES} bytes"
                        )
                    detached_atlas_bundles.append(detached_bundle)
                    retained_atlas_replay_addresses.append(replay_input_address)
                    retained_atlas_addresses.append(atlas_address)
                atlas_bundles = tuple(detached_atlas_bundles)
                atlas_replay_input_addresses = tuple(retained_atlas_replay_addresses)
                atlas_bundle_addresses = tuple(retained_atlas_addresses)
                source_receipts += tuple(
                    receipt.to_dict() for bundle in atlas_bundles for receipt in bundle.receipts
                )
                if len(source_receipts) != source_receipt_count:
                    raise ValidationError("source receipt accounting is inconsistent")
                atlas_claims, atlas_link_warnings = self._link_atlas_claims(
                    build_manifest,
                    atlas_bundles,
                    max_claims=atlas_external_claim_max,
                )
                if len(atlas_claims) != atlas_claim_observation_count:
                    raise ValidationError("atlas claim accounting is inconsistent")
                if atlas_link_warnings != tuple(projected_link_warnings):
                    raise ValidationError("atlas link warning accounting is inconsistent")
                atlas_warnings = tuple(atlas_warning_values)
                atlas_event_warnings = tuple(dict.fromkeys(atlas_warnings + atlas_link_warnings))
                runtime_warnings = tuple(dict.fromkeys(runtime_warnings + atlas_event_warnings))
                if len(runtime_warnings) > validator_limits.max_sequence_items:
                    raise ValidationError(
                        "warnings exceeds the configured maximum of "
                        f"{validator_limits.max_sequence_items} items"
                    )
                self._validate_event_payload_size(
                    {
                        "replay_input_addresses": list(atlas_replay_input_addresses),
                        "bundle_addresses": list(atlas_bundle_addresses),
                        "claim_count": len(atlas_claims),
                        "warnings": list(atlas_event_warnings),
                    },
                    "public atlas",
                )
                self._validate_manifest_contract(
                    build_manifest,
                    "post-atlas case manifest",
                )
        if adapter_ids:
            registry = configured_adapter_registry
            if registry is None or type(registry) is not AdapterRegistry:
                raise ValidationError("adapter registry configuration is invalid")
            adapter_base_manifest = build_manifest
            retained_adapter_addresses: list[str] = []
            adapter_base_address, source_closure_bytes = self._retain_source_record(
                source_records,
                adapter_base_manifest.to_dict(),
                source_closure_bytes,
                label="adapter base manifest",
                record_ceiling=validator_limits.max_source_bundles,
                reserved_records=reserved_source_records,
                object_max_bytes=persisted_object_max_bytes,
                source_closure_max_bytes=source_closure_max_bytes,
            )
            retained_adapter_addresses.append(adapter_base_address)
            self._require_source_callback_capacity(
                source_closure_bytes,
                source_records,
                record_ceiling=validator_limits.max_source_bundles,
                reserved_records=reserved_source_records,
                source_closure_max_bytes=source_closure_max_bytes,
            )
            adapter_registry_snapshot = configuration.selected_adapter_snapshot
            adapter_registry_entries = configuration.selected_adapter_entries
            if adapter_registry_snapshot is None or not adapter_registry_entries:
                raise ValidationError("captured adapter registry selection is incomplete")
            adapter_registry_address, source_closure_bytes = self._retain_source_record(
                source_records,
                adapter_registry_snapshot.to_dict(),
                source_closure_bytes,
                label="adapter registry snapshot",
                record_ceiling=validator_limits.max_source_bundles,
                reserved_records=reserved_source_records,
                object_max_bytes=persisted_object_max_bytes,
                source_closure_max_bytes=source_closure_max_bytes,
            )
            retained_adapter_addresses.append(adapter_registry_address)
            self._require_source_callback_capacity(
                source_closure_bytes,
                source_records,
                record_ceiling=validator_limits.max_source_bundles,
                reserved_records=reserved_source_records,
                source_closure_max_bytes=source_closure_max_bytes,
            )
            adapter_resolution = AdapterRegistry.resolve_manifest_entries(
                registry,
                adapter_base_manifest,
                adapter_registry_snapshot,
                adapter_registry_entries,
                after_callback=lambda: assert_evaluation_configuration(configuration, guard_state),
            )
            assert_evaluation_configuration(configuration, guard_state)
            if adapter_resolution.registry_address != adapter_registry_snapshot.content_address:
                raise ValidationError("adapter registry snapshot changed during resolution")
            adapter_resolution_address, source_closure_bytes = self._retain_source_record(
                source_records,
                adapter_resolution.to_dict(),
                source_closure_bytes,
                label="adapter resolution report",
                record_ceiling=validator_limits.max_source_bundles,
                reserved_records=reserved_source_records,
                object_max_bytes=persisted_object_max_bytes,
                source_closure_max_bytes=source_closure_max_bytes,
            )
            retained_adapter_addresses.append(adapter_resolution_address)
            self._require_source_callback_capacity(
                source_closure_bytes,
                source_records,
                record_ceiling=validator_limits.max_source_bundles,
                reserved_records=reserved_source_records,
                source_closure_max_bytes=source_closure_max_bytes,
            )
            adapter_budget_manifest = replace(
                adapter_base_manifest,
                candidate_elements=self._merge_adapter_elements(
                    adapter_base_manifest,
                    adapter_resolution,
                ),
            )
            adapter_budget_probe = builder.build(
                adapter_budget_manifest,
                self._run_id(adapter_budget_manifest, rna_rows),
                rna_consequences=rna_rows,
                retained_owner_address=rna_input_address,
                external_claims=atlas_claims,
            )
            adapter_baseline_claim_count = len(adapter_budget_probe.claims)
            if adapter_baseline_claim_count > validator_limits.max_evidence_claims:
                raise ValidationError(
                    "pre-adapter evidence claims exceed the configured maximum of "
                    f"{validator_limits.max_evidence_claims} items"
                )
            adapter_baseline_by_edge: dict[str, int] = {}
            for claim in adapter_budget_probe.claims:
                adapter_baseline_by_edge[claim.edge_id] = (
                    adapter_baseline_by_edge.get(claim.edge_id, 0) + 1
                )
            if any(
                count > validator_limits.max_claims_per_edge
                for count in adapter_baseline_by_edge.values()
            ):
                raise ValidationError(
                    "pre-adapter evidence claims exceed the configured per-edge maximum of "
                    f"{validator_limits.max_claims_per_edge} items"
                )
            adapter_graph_edge_ids = {
                edge.edge_id
                for hypothesis in adapter_budget_probe.hypotheses
                for edge in hypothesis.edges
            }
            adapter_claim_allowance_by_edge = {
                edge_id: (
                    validator_limits.max_claims_per_edge - adapter_baseline_by_edge.get(edge_id, 0)
                )
                for edge_id in adapter_graph_edge_ids
            }
            adapter_claim_allowance = min(
                external_claim_max - len(atlas_claims),
                validator_limits.max_evidence_claims - adapter_baseline_claim_count,
            )
            adapter_claim_report = AdapterRegistry.collect_claims_entries(
                registry,
                adapter_base_manifest,
                adapter_resolution,
                adapter_registry_snapshot,
                adapter_registry_entries,
                max_claims=adapter_claim_allowance,
                max_claims_by_edge=adapter_claim_allowance_by_edge,
                after_callback=lambda: assert_evaluation_configuration(configuration, guard_state),
            )
            assert_evaluation_configuration(configuration, guard_state)
            if adapter_claim_report.registry_snapshot != adapter_registry_snapshot:
                raise ValidationError("adapter registry snapshot changed during claim collection")
            adapter_claim_address, source_closure_bytes = self._retain_source_record(
                source_records,
                adapter_claim_report.to_dict(),
                source_closure_bytes,
                label="adapter claim collection report",
                record_ceiling=validator_limits.max_source_bundles,
                reserved_records=reserved_source_records,
                object_max_bytes=persisted_object_max_bytes,
                source_closure_max_bytes=source_closure_max_bytes,
            )
            retained_adapter_addresses.append(adapter_claim_address)
            adapter_source_addresses = tuple(retained_adapter_addresses)
            build_manifest = self._materialize_adapter_manifest(
                adapter_base_manifest,
                adapter_resolution,
                adapter_source_addresses,
            )
            self._validate_manifest_contract(build_manifest, "adapter-enriched case manifest")
            builder.validate_inputs(
                build_manifest,
                rna_consequences=rna_rows,
            )
            adapter_claims = adapter_claim_report.claims
        if len(adapter_claims) > external_claim_max - len(atlas_claims):
            raise ValidationError(
                f"external_claims exceeds the configured maximum of {external_claim_max} items"
            )
        source_bundle_addresses = tuple(source_records)
        if len(source_bundle_addresses) + reserved_source_records > (
            validator_limits.max_source_bundles
        ):
            raise ValidationError(
                "source_bundle_addresses exceeds the configured maximum of "
                f"{validator_limits.max_source_bundles} items"
            )

        run_id = self._run_id(build_manifest, rna_rows)
        if live_reference and (self.store.runs / f"{run_id}.json").exists():
            conflict = StoreError(f"run already exists: {run_id}")
            raise ValidationError(f"run publication failed: {conflict}") from conflict
        log = EventLog(run_id)
        input_record = build_manifest.to_dict()
        input_address = content_hash(input_record)
        case_received_payload: dict[str, Any] = {
            "input_address": input_address,
            "case_id": manifest.case_id,
        }
        if rna_input is not None:
            if rna_input_address is None:  # pragma: no cover - built as one atomic branch
                raise ValidationError("RNA input preparation is incomplete")
            case_received_payload.update(
                {
                    "rna_input_address": rna_input_address,
                    "rna_consequence_count": len(rna_rows),
                }
            )
        if source_closure_bytes > source_closure_max_bytes:  # pragma: no cover - incremental
            raise ValidationError(
                "source record closure exceeds its aggregate canonical byte ceiling"
            )
        log.append(
            "case_received",
            case_received_payload,
            event_id=f"evt-{run_id}-received",
        )
        if live_reference:
            if (
                enrichment is None or reference_event_payload is None
            ):  # pragma: no cover - guarded by live preparation
                raise ValidationError("live reference preparation is incomplete")
            try:
                log.append(
                    "public_reference_enriched",
                    reference_event_payload,
                    event_id=f"evt-{run_id}-reference",
                )
            except ValueError as exc:
                raise ValidationError("public reference event could not be recorded") from exc
            if atlas_bundle_addresses:
                atlas_event_payload = {
                    "replay_input_addresses": list(atlas_replay_input_addresses),
                    "bundle_addresses": list(atlas_bundle_addresses),
                    "claim_count": len(atlas_claims),
                    "warnings": list(atlas_event_warnings),
                }
                self._validate_event_payload_size(atlas_event_payload, "public atlas")
                try:
                    log.append(
                        "public_atlas_collected",
                        atlas_event_payload,
                        event_id=f"evt-{run_id}-atlas",
                    )
                except ValueError as exc:
                    raise ValidationError("public atlas event could not be recorded") from exc
        if adapter_resolution is not None and adapter_claim_report is not None:
            log.append(
                "adapter_evidence_collected",
                {
                    "adapter_ids": list(adapter_resolution.adapter_ids),
                    "base_input_address": adapter_resolution.manifest_address,
                    "effective_input_address": input_address,
                    "registry_bundle_address": adapter_source_addresses[1],
                    "registry_address": adapter_resolution.registry_address,
                    "resolution_bundle_address": adapter_source_addresses[2],
                    "resolution_address": adapter_resolution.content_address,
                    "claim_collection_bundle_address": adapter_source_addresses[3],
                    "claim_collection_address": adapter_claim_report.content_address,
                    "resolved_element_count": adapter_resolution.element_count,
                    "attribution_count": adapter_claim_report.attribution_count,
                    "claim_count": adapter_claim_report.claim_count,
                    "source_bundle_addresses": list(adapter_source_addresses),
                },
                event_id=f"evt-{run_id}-adapters",
            )
        assert_evaluation_configuration(configuration, guard_state)
        built = builder.build(
            build_manifest,
            run_id,
            rna_consequences=rna_rows,
            retained_owner_address=rna_input_address,
            external_claims=atlas_claims + adapter_claims,
        )
        if adapter_resolution is not None and adapter_claim_report is not None:
            adapter_claim_report.validate_claim_ownership(adapter_resolution)
            reported_adapter_claim_ids = frozenset(
                claim.evidence_id for claim in adapter_claim_report.claims
            )
            if any(
                claim.produced_by in adapter_claim_report.adapter_ids
                and claim.evidence_id not in reported_adapter_claim_ids
                for claim in built.claims
            ):
                raise ValidationError(
                    "adapter IDs collide with native evidence producer identities"
                )
        all_warnings = tuple(dict.fromkeys(tuple(built.warnings) + runtime_warnings))
        if len(all_warnings) > validator_limits.max_sequence_items:
            raise ValidationError(
                "warnings exceeds the configured maximum of "
                f"{validator_limits.max_sequence_items} items"
            )
        built_event_payload = {
            "hypothesis_count": len(built.hypotheses),
            "claim_count": len(built.claims),
            "warnings": list(all_warnings),
        }
        self._validate_event_payload_size(built_event_payload, "hypotheses built")
        try:
            log.append(
                "hypotheses_built",
                built_event_payload,
                event_id=f"evt-{run_id}-built",
            )
        except ValueError as exc:
            raise ValidationError("hypotheses-built event could not be recorded") from exc
        experiments = planner.plan_many(built.hypotheses)
        log.append(
            "validation_routes_planned",
            {"experiment_count": len(experiments)},
            event_id=f"evt-{run_id}-planned",
        )
        declared_source_addresses = (
            source_bundle_addresses
            if rna_input_address is None
            else (rna_input_address, *source_bundle_addresses)
        )
        dossier = self._make_dossier(
            manifest=build_manifest,
            run_id=run_id,
            input_address=input_address,
            hypotheses=built.hypotheses,
            claims=built.claims,
            experiments=experiments,
            review=None,
            status=ResearchStatus.REVIEW_REQUIRED,
            event_head=log.head,
            warnings=all_warnings,
            source_receipts=source_receipts,
            source_bundle_addresses=declared_source_addresses,
        )
        self._validate_dossier_contract(dossier, "draft dossier")
        decision = self._policy_dossier_decision(dossier, "draft dossier")
        if not decision.allowed:
            raise PolicyViolation("; ".join(decision.violations))
        log.append(
            "dossier_created", {"dossier_id": dossier.dossier_id}, event_id=f"evt-{run_id}-dossier"
        )
        dossier = self._readdress(replace(dossier, event_head=log.head))
        self._validate_dossier_contract(dossier, "final dossier")
        if not live_reference:
            reused = self._reuse_untouched_offline_draft(dossier, log)
            if reused is not None:
                return reused
        assert_evaluation_configuration(configuration, guard_state)
        for address, source_record in source_records.items():
            if self.store.store.put_at(address, source_record) != address:
                raise ValidationError("source bundle address changed during evaluation")
        if self.store.store.put(input_record) != input_address:
            raise ValidationError("manifest input address changed during evaluation")
        if rna_input is not None:
            expected_rna_address = case_received_payload["rna_input_address"]
            if self.store.store.put(rna_input) != expected_rna_address:
                raise ValidationError("RNA input address changed during evaluation")
        try:
            self._persist(build_manifest, log, dossier, input_address)
        except ValidationError as exc:
            cause = exc.__cause__
            exact_create_conflict = (
                not live_reference
                and type(cause) is StoreError
                and str(cause) == f"run already exists: {run_id}"
            )
            if not exact_create_conflict:
                raise
            reused = self._reuse_untouched_offline_draft(dossier, log)
            if reused is None:  # pragma: no cover - create conflict requires an index
                raise
            return reused
        self._logs[run_id] = log
        return dossier

    @staticmethod
    def _reject_reserved_adapter_versions(manifest: CaseManifest, label: str) -> None:
        reserved = tuple(
            sorted(set(manifest.input_versions).intersection(_ADAPTER_INPUT_VERSION_KEYS))
        )
        if reserved:
            raise ValidationError(
                f"{label} uses runtime-reserved adapter input_versions: {list(reserved)}"
            )

    def review(self, dossier: Dossier, review: ReviewDecision) -> Dossier:
        """Attach a review decision and create a new immutable dossier snapshot."""

        self._validate_dossier_contract(dossier, "source dossier")
        persisted, staged_log, run_record = self._load_current_snapshot(dossier.run_id)
        if canonical_bytes(dossier.to_dict()) != canonical_bytes(persisted.to_dict()):
            raise ValidationError("dossier is not the current persisted run snapshot")
        return self._review_candidate(
            dossier,
            review,
            staged_log=staged_log,
            expected_run=run_record,
        )

    def review_run(self, run_id: str, review: ReviewDecision) -> Dossier:
        """Reopen a persisted run, attach a review, and persist a new snapshot."""

        dossier, staged_log, run_record = self._load_current_snapshot(run_id)
        return self._review_candidate(
            dossier,
            review,
            staged_log=staged_log,
            expected_run=run_record,
        )

    def _review_candidate(
        self,
        dossier: Dossier,
        review: ReviewDecision,
        *,
        staged_log: EventLog,
        expected_run: dict[str, Any],
    ) -> Dossier:
        """Build and commit one review against a detached, verified event log."""

        self._require_exact_policy()
        self._validate_review_input(dossier, review)
        self._append_snapshot_predecessor_binding(staged_log, expected_run)
        staged_log.append("review_recorded", review.to_dict(), event_id=review.review_id)
        status = (
            ResearchStatus.RELEASED_RESEARCH
            if review.state is ReviewState.ACCEPTED
            else ResearchStatus.REVIEWED
        )
        updated = self._make_dossier(
            manifest=None,
            run_id=dossier.run_id,
            input_address=dossier.input_address,
            hypotheses=dossier.hypotheses,
            claims=dossier.evidence,
            experiments=dossier.experiments,
            review=review,
            status=status,
            event_head=staged_log.head,
            warnings=dossier.warnings,
            case_id=dossier.case_id,
            created_at=dossier.created_at,
            source_receipts=dossier.source_receipts,
            source_bundle_addresses=dossier.source_bundle_addresses,
        )
        self._validate_dossier_contract(updated, "reviewed dossier")
        decision = self._policy_dossier_decision(updated, "reviewed dossier")
        if not decision.allowed:
            raise PolicyViolation("; ".join(decision.violations))
        if review.state is ReviewState.ACCEPTED:
            self._check_release(updated, "release gate")
        self._persist(
            None,
            staged_log,
            updated,
            dossier.input_address,
            expected_run=expected_run,
        )
        self._logs[dossier.run_id] = staged_log
        return updated

    def _validate_review_input(self, dossier: Dossier, review: ReviewDecision) -> None:
        """Reject forged, oversized, or snapshot-incomplete reviews before staging."""

        validator = self._require_exact_validator(self.validator, "runtime validator")
        if type(review) is not ReviewDecision:
            raise ValidationError("review must be an exact ReviewDecision")
        if type(review.state) is not ReviewState:
            raise ValidationError("review state must be an exact ReviewState")
        scalar_values = (
            review.review_id,
            review.case_id,
            review.reviewer,
            review.rationale,
            review.created_at,
        )
        if any(type(value) is not str for value in scalar_values):
            raise ValidationError("review scalar fields must be exact strings")
        if type(review.reviewed_hypothesis_ids) is not tuple or any(
            type(value) is not str for value in review.reviewed_hypothesis_ids
        ):
            raise ValidationError("reviewed_hypothesis_ids must be an exact tuple of strings")
        if type(review.checked_claim_ids) is not tuple or any(
            type(value) is not str for value in review.checked_claim_ids
        ):
            raise ValidationError("checked_claim_ids must be an exact tuple of strings")
        if len(review.reviewed_hypothesis_ids) > len(dossier.hypotheses):
            raise ValidationError("review names more hypotheses than the current snapshot contains")
        if len(review.checked_claim_ids) > len(dossier.evidence):
            raise ValidationError("review names more claims than the current snapshot contains")
        all_strings = (
            *scalar_values,
            *review.reviewed_hypothesis_ids,
            *review.checked_claim_ids,
        )
        limits = validator.limits
        if any(len(value) > limits.max_string_characters for value in all_strings):
            raise ValidationError("review contains a string that exceeds validation limits")
        if sum(len(value) for value in all_strings) > limits.max_total_characters:
            raise ValidationError("review strings exceed aggregate validation limits")
        try:
            raw = review.to_dict()
            canonical = ReviewDecision.from_dict(raw, persisted=True)
            if canonical_bytes(raw) != canonical_bytes(canonical.to_dict()):
                raise ValidationError("review does not round-trip exactly")
        except Exception as exc:  # noqa: BLE001 - hostile review objects fail closed
            raise ValidationError("review is not an exact canonical ReviewDecision") from exc
        if review.case_id != dossier.case_id:
            raise ValidationError("review case_id does not match dossier")
        known_hypotheses = {hypothesis.hypothesis_id for hypothesis in dossier.hypotheses}
        reviewed_hypotheses = set(review.reviewed_hypothesis_ids)
        unknown_hypotheses = reviewed_hypotheses - known_hypotheses
        if unknown_hypotheses:
            raise ValidationError(f"review names unknown hypotheses: {sorted(unknown_hypotheses)}")
        known_claims = {claim.evidence_id for claim in dossier.evidence}
        checked_claims = set(review.checked_claim_ids)
        unknown_claims = checked_claims - known_claims
        if unknown_claims:
            raise ValidationError(f"review names unknown claims: {sorted(unknown_claims)}")
        if review.state is ReviewState.ACCEPTED:
            if reviewed_hypotheses != known_hypotheses:
                raise ValidationError(
                    "accepted review must cover every hypothesis in the current snapshot"
                )
            if checked_claims != known_claims:
                raise ValidationError(
                    "accepted review must cover every evidence claim in the current snapshot"
                )

    def _persisted_object_max_bytes(self) -> int:
        validator = self._require_exact_validator(self.validator, "runtime validator")
        return validator.limits.max_canonical_bytes

    def _persisted_source_receipt_max(self) -> int:
        validator = self._require_exact_validator(self.validator, "runtime validator")
        return min(
            validator.limits.max_source_receipts,
            validator.limits.max_sequence_items,
        )

    @property
    def persisted_object_max_bytes(self) -> int:
        """Return the revalidated canonical-object ceiling used by runtime loaders."""

        return self._persisted_object_max_bytes()

    @property
    def source_closure_max_bytes(self) -> int:
        """Return the aggregate canonical-byte ceiling for persisted source records."""

        return self._source_closure_max_bytes

    def load_manifest(self, input_address: str) -> CaseManifest:
        """Load one bounded, address-closed, exact persisted case manifest."""

        try:
            raw = self.store.store.get_verified(
                input_address,
                max_bytes=self._persisted_object_max_bytes(),
            )
            if type(raw) is not dict:
                raise ValidationError("persisted manifest input must be an exact object")
            manifest = CaseManifest.from_dict(raw)
            if manifest.content_address != input_address or canonical_bytes(
                manifest.to_dict()
            ) != canonical_bytes(raw):
                raise ValidationError("persisted manifest input does not round-trip exactly")
            self._validate_manifest_contract(manifest, "persisted manifest input")
            return manifest
        except Exception as exc:  # noqa: BLE001 - stored inputs are hostile
            if isinstance(exc, ValidationError):
                raise
            raise ValidationError("persisted manifest input object is missing or invalid") from exc

    def load_event_log(self, event_address: str) -> EventLog:
        """Load one bounded, address-closed, exact persisted event log."""

        try:
            raw = self.store.store.get_verified(
                event_address,
                max_bytes=MAX_EVENT_RECORD_BYTES,
            )
            if type(raw) is not dict:
                raise ValidationError("persisted event record must be an exact object")
            log = EventLog.from_record(raw, expected_address=event_address)
            if not log.verify() or canonical_bytes(log.to_record()) != canonical_bytes(raw):
                raise ValidationError("persisted event record does not round-trip exactly")
            return log
        except Exception as exc:  # noqa: BLE001 - stored events are hostile
            if isinstance(exc, ValidationError):
                raise
            raise ValidationError("persisted run has a missing or invalid event record") from exc

    def load_dossier(self, dossier_address: str) -> Dossier:
        """Load one bounded, canonical, exact persisted dossier snapshot."""

        try:
            source_receipt_max = self._persisted_source_receipt_max()
            raw = self.store.store.get_canonical(
                dossier_address,
                max_bytes=self._persisted_object_max_bytes(),
            )
            if type(raw) is not dict:
                raise ValidationError("persisted dossier must be an exact object")
            raw_source_receipts = raw.get("source_receipts")
            if (
                type(raw_source_receipts) is list
                and len(raw_source_receipts) > source_receipt_max
            ):
                raise ValidationError(
                    "persisted source_receipts exceeds the configured maximum of "
                    f"{source_receipt_max} items"
                )
            dossier = Dossier.from_dict(raw)
            if (
                dossier.content_address != dossier_address
                or self._dossier_address(dossier) != dossier_address
                or canonical_bytes(dossier.to_dict()) != canonical_bytes(raw)
            ):
                raise ValidationError("persisted dossier does not round-trip exactly")
            self._validate_dossier_contract(dossier, "persisted dossier")
            return dossier
        except Exception as exc:  # noqa: BLE001 - stored dossiers are hostile
            if isinstance(exc, ValidationError):
                raise
            raise ValidationError(
                "persisted dossier is missing or invalid; run has invalid persisted artifacts"
            ) from exc

    def load_run_snapshot(self, run_id: str) -> VerifiedRunSnapshot:
        """Load the current typed run closure and require complete replay integrity."""

        # Keep an absent/invalid run index distinguishable from corruption of an
        # existing run's referenced immutable objects.
        run_record = self.get_run(run_id)
        return self._load_run_snapshot_record(run_id, run_record)

    def load_run_snapshot_at(
        self,
        run_id: str,
        *,
        event_address: str,
        dossier_address: str,
    ) -> VerifiedRunSnapshot:
        """Reopen one paired immutable snapshot retained in a run's append-only history."""

        selected_event = _runtime_sha256_address(
            event_address,
            "historical snapshot event_address",
        )
        selected_dossier = _runtime_sha256_address(
            dossier_address,
            "historical snapshot dossier_address",
        )
        current = self.get_run(run_id)
        current_snapshot = self._load_run_snapshot_record(run_id, current)
        current_record = current_snapshot.run_record_dict()
        event_history = current_record["event_history"]
        dossier_history = current_record["dossier_history"]
        if type(event_history) is not list or type(dossier_history) is not list:
            raise ValidationError("run history must contain exact address arrays")
        if (
            not event_history
            or not dossier_history
            or len(event_history) != len(set(event_history))
            or len(dossier_history) != len(set(dossier_history))
            or event_history[-1] != current_record["event_address"]
            or dossier_history[-1] != current_record["dossier_address"]
        ):
            raise ValidationError("run histories must be unique and current-ended")
        if len(event_history) > len(dossier_history):
            raise ValidationError("run event and dossier histories cannot be paired")
        # Supported legacy indexes may retain dossiers that predate event-history
        # persistence. Every recorded event still pairs unambiguously with the
        # same-position item in the right-aligned dossier suffix; older dossier-only
        # entries intentionally remain unavailable through this API.
        dossier_offset = len(dossier_history) - len(event_history)
        try:
            event_index = event_history.index(selected_event)
            dossier_index = dossier_history.index(selected_dossier)
        except ValueError as exc:
            raise ValidationError("requested snapshot is absent from the run history") from exc
        if dossier_index != event_index + dossier_offset:
            raise ValidationError("requested event and dossier addresses are not a paired snapshot")
        if (
            selected_event == current_record["event_address"]
            and selected_dossier == current_record["dossier_address"]
        ):
            return current_snapshot
        historical = dict(current_record)
        historical["event_address"] = selected_event
        historical["dossier_address"] = selected_dossier
        historical["event_history"] = event_history[: event_index + 1]
        historical["dossier_history"] = dossier_history[: dossier_index + 1]
        selected_snapshot = self._load_run_snapshot_record(run_id, historical)
        selected_events = selected_snapshot.event_log.to_record()["events"]
        current_events = current_snapshot.event_log.to_record()["events"]
        if len(selected_events) >= len(current_events) or canonical_bytes(
            selected_events
        ) != canonical_bytes(current_events[: len(selected_events)]):
            raise ValidationError(
                "requested historical event log is not an ancestor of the current run"
            )
        successor = current_events[len(selected_events)]
        if (
            type(successor) is not dict
            or successor.get("event_type") != "snapshot_predecessor_bound"
        ):
            raise ValidationError(
                "requested historical snapshot has no authenticated successor binding"
            )
        bound_pair = self._snapshot_predecessor_pair(successor, run_id=run_id)
        if bound_pair != (selected_event, selected_dossier):
            raise ValidationError(
                "requested historical snapshot does not match its successor binding"
            )
        return selected_snapshot

    @staticmethod
    def _snapshot_predecessor_pair(
        event: Mapping[str, Any],
        *,
        run_id: str,
        expected_event_address: str | None = None,
    ) -> tuple[str, str]:
        """Validate one canonical predecessor event and return its bound pair."""

        if (
            type(event) is not dict
            or event.get("event_type") != "snapshot_predecessor_bound"
            or type(event.get("payload")) is not dict
        ):
            raise ValidationError("snapshot predecessor binding has a non-canonical shape")
        payload = event["payload"]
        if set(payload) != _SNAPSHOT_PREDECESSOR_FIELDS:
            raise ValidationError("snapshot predecessor binding has a non-canonical shape")
        previous_event = _runtime_sha256_address(
            payload.get("previous_event_address"),
            "snapshot predecessor previous_event_address",
        )
        previous_dossier = _runtime_sha256_address(
            payload.get("previous_dossier_address"),
            "snapshot predecessor previous_dossier_address",
        )
        body = {
            "version": _SNAPSHOT_PREDECESSOR_VERSION,
            "run_id": run_id,
            "previous_event_address": previous_event,
            "previous_dossier_address": previous_dossier,
        }
        expected_binding = content_hash(body, prefix="snapshot-predecessor")
        binding_digest = expected_binding.rsplit(":", 1)[1]
        expected_event_id = f"evt-{run_id}-predecessor-{binding_digest[:20]}"
        if (
            payload.get("version") != _SNAPSHOT_PREDECESSOR_VERSION
            or payload.get("run_id") != run_id
            or payload.get("binding_address") != expected_binding
            or event.get("event_id") != expected_event_id
        ):
            raise ValidationError("snapshot predecessor binding does not verify")
        if expected_event_address is not None and previous_event != expected_event_address:
            raise ValidationError(
                "snapshot predecessor binding does not address its exact event prefix"
            )
        return previous_event, previous_dossier

    def _validate_retained_snapshot_history(
        self,
        run_id: str,
        run_record: Mapping[str, Any],
        log: EventLog,
    ) -> None:
        """Authenticate the retained modern history suffix from binding events."""

        event_history = run_record["event_history"]
        dossier_history = run_record["dossier_history"]
        dossier_offset = len(dossier_history) - len(event_history)
        retained_pairs = tuple(zip(event_history, dossier_history[dossier_offset:], strict=True))
        event_rows = log.to_record()["events"]
        empty_record = canonical_bytes({"events": [], "run_id": run_id})
        record_prefix, marker, record_suffix = empty_record.partition(b"[]")
        if marker != b"[]":  # pragma: no cover - canonical serializer invariant
            raise ValidationError("cannot derive the canonical event-record envelope")
        prefix_hasher = hashlib.sha256(record_prefix + b"[")
        record_tail = b"]" + record_suffix

        bindings: list[tuple[str, str]] = []
        binding_indexes: list[int] = []
        for index, event in enumerate(event_rows):
            if event.get("event_type") == "snapshot_predecessor_bound":
                prefix_probe = prefix_hasher.copy()
                prefix_probe.update(record_tail)
                expected_prefix_address = f"sha256:{prefix_probe.hexdigest()}"
                pair = self._snapshot_predecessor_pair(
                    event,
                    run_id=run_id,
                    expected_event_address=expected_prefix_address,
                )
                if (
                    index + 1 >= len(event_rows)
                    or event_rows[index + 1].get("event_type")
                    not in _SNAPSHOT_SUCCESSOR_EVENT_TYPES
                ):
                    raise ValidationError(
                        "snapshot predecessor binding must immediately precede one transition"
                    )
                if binding_indexes and index != binding_indexes[-1] + 2:
                    raise ValidationError(
                        "modern snapshot transitions must form one contiguous event suffix"
                    )
                bindings.append(pair)
                binding_indexes.append(index)
            if index:
                prefix_hasher.update(b",")
            prefix_hasher.update(canonical_bytes(event))

        if not bindings:
            return
        if binding_indexes[-1] != len(event_rows) - 2:
            raise ValidationError("modern snapshot transitions must end at the current event head")
        modern_pairs = (*bindings, (run_record["event_address"], run_record["dossier_address"]))
        if len(modern_pairs) != len(set(modern_pairs)):
            raise ValidationError("modern snapshot predecessor pairs must be unique")

        overlap = min(len(retained_pairs), len(modern_pairs))
        if retained_pairs[-overlap:] != modern_pairs[-overlap:]:
            raise ValidationError(
                "retained run history does not match its authenticated modern suffix"
            )

    def _validate_persisted_review_events(
        self,
        dossier: Dossier,
        log: EventLog,
    ) -> None:
        """Close typed review and assignment events over the current dossier."""

        latest_review: ReviewDecision | None = None
        for event in log.all():
            if event.event_type == "review_recorded":
                raw_review = event.to_dict()["payload"]
                try:
                    review = ReviewDecision.from_dict(raw_review, persisted=True)
                except (TypeError, ValueError, ValidationError) as exc:
                    raise ValidationError(
                        "persisted review event payload is not a canonical ReviewDecision"
                    ) from exc
                if (
                    canonical_bytes(review.to_dict()) != canonical_bytes(raw_review)
                    or event.event_id != review.review_id
                    or review.case_id != dossier.case_id
                ):
                    raise ValidationError(
                        "persisted review event does not match its canonical identity"
                    )
                self._validate_review_input(dossier, review)
                latest_review = review
            elif event.event_type == "review_assigned":
                if latest_review is not None and latest_review.state in {
                    ReviewState.ACCEPTED,
                    ReviewState.REJECTED,
                }:
                    raise ValidationError(
                        "persisted assignment cannot follow a terminal review decision"
                    )
                self._validate_persisted_assignment_event(dossier, event.to_dict())

        if (latest_review is None) != (dossier.review is None):
            raise ValidationError(
                "persisted dossier review presence does not match its event history"
            )
        if latest_review is not None and (
            dossier.review is None
            or canonical_bytes(latest_review.to_dict()) != canonical_bytes(dossier.review.to_dict())
        ):
            raise ValidationError("persisted dossier review does not match the latest review event")

    def _validate_persisted_assignment_event(
        self,
        dossier: Dossier,
        event: Mapping[str, Any],
    ) -> None:
        """Validate the complete addressed payload of one assignment event."""

        if type(event) is not dict or type(event.get("payload")) is not dict:
            raise ValidationError("persisted assignment event must be an exact object")
        payload = event["payload"]
        if set(payload) != _REVIEW_ASSIGNMENT_FIELDS or any(
            type(payload.get(field)) is not str for field in _REVIEW_ASSIGNMENT_FIELDS
        ):
            raise ValidationError("persisted assignment event has a non-canonical payload")
        required = ("assignment_id", "run_id", "case_id", "reviewer", "queue_id", "created_at")
        if any(not payload[field].strip() for field in required):
            raise ValidationError("persisted assignment event has an empty required field")
        if any(fragment in payload["assignment_id"] for fragment in ("/", "\\", "..")):
            raise ValidationError("persisted assignment event has an unsafe identifier")
        try:
            created_at = datetime.fromisoformat(payload["created_at"])
        except ValueError as exc:
            raise ValidationError(
                "persisted assignment created_at must be an ISO 8601 timestamp"
            ) from exc
        if (
            created_at.tzinfo is None
            or created_at.utcoffset() != timedelta(0)
            or created_at.isoformat() != payload["created_at"]
        ):
            raise ValidationError("persisted assignment created_at must use canonical UTC spelling")
        body = {key: value for key, value in payload.items() if key != "content_address"}
        if (
            event.get("event_id") != payload["assignment_id"]
            or payload["run_id"] != dossier.run_id
            or payload["case_id"] != dossier.case_id
            or payload["content_address"] != content_hash(body, prefix="review-assignment")
        ):
            raise ValidationError(
                "persisted assignment event does not match its canonical identity"
            )
        self._enforce_policy_texts(tuple(body.values()), "persisted review assignment")

    @staticmethod
    def _append_snapshot_predecessor_binding(
        log: EventLog,
        expected_run: Mapping[str, Any],
    ) -> None:
        """Bind the predecessor event/dossier pair into the immutable successor log."""

        if type(log) is not EventLog or type(expected_run) is not dict:
            raise ValidationError("snapshot predecessor binding requires exact runtime inputs")
        run_id = expected_run.get("run_id")
        if type(run_id) is not str or log.run_id != run_id:
            raise ValidationError("snapshot predecessor binding run_id is inconsistent")
        event_address = _runtime_sha256_address(
            expected_run.get("event_address"),
            "snapshot predecessor event_address",
        )
        dossier_address = _runtime_sha256_address(
            expected_run.get("dossier_address"),
            "snapshot predecessor dossier_address",
        )
        if log.record_address != event_address:
            raise ValidationError(
                "snapshot predecessor event address does not match the staged log"
            )
        body = {
            "version": _SNAPSHOT_PREDECESSOR_VERSION,
            "run_id": run_id,
            "previous_event_address": event_address,
            "previous_dossier_address": dossier_address,
        }
        binding_address = content_hash(body, prefix="snapshot-predecessor")
        log.append(
            "snapshot_predecessor_bound",
            body | {"binding_address": binding_address},
            event_id=(f"evt-{run_id}-predecessor-{binding_address.rsplit(':', 1)[1][:20]}"),
        )

    def _load_run_snapshot_record(
        self,
        run_id: str,
        run_record: Mapping[str, Any],
    ) -> VerifiedRunSnapshot:
        """Hydrate and semantically verify one current-ended run record."""

        if type(run_record) is not dict:
            raise ValidationError("verified run record must be an exact object")
        try:
            event_address = run_record["event_address"]
            dossier_address = run_record["dossier_address"]
            input_address = run_record["input_address"]
            log = self.load_event_log(event_address)
            dossier = self.load_dossier(dossier_address)
            manifest = self.load_manifest(input_address)
            event_record = log.to_record()
            dossier_record = dossier.to_dict()
            replay = ReplayVerifier().verify(run_record, event_record, dossier_record)
            if not replay.event_chain_valid or not replay.stored_dossier_matches_address:
                raise ValidationError("persisted run failed replay integrity")
            if dossier.run_id != run_id or log.run_id != run_id or replay.run_id != run_id:
                raise ValidationError("persisted run identifier is inconsistent")
            if dossier.event_head != log.head:
                raise ValidationError("persisted dossier does not close over the event log")
            self._validate_persisted_run_inputs(
                dossier=dossier,
                log=log,
                input_record=manifest.to_dict(),
                input_address=input_address,
            )
            snapshot = VerifiedRunSnapshot(
                run_record=run_record,
                manifest=manifest,
                event_record=event_record,
                dossier=dossier,
                replay=replay,
            )
            self._validate_retained_snapshot_history(run_id, snapshot.run_record, log)
            return snapshot
        except Exception as exc:  # noqa: BLE001 - persisted hostile data must fail closed
            if isinstance(exc, ValidationError):
                raise
            raise ValidationError("cannot load a run with invalid persisted artifacts") from exc

    def _load_current_snapshot(
        self,
        run_id: str,
    ) -> tuple[Dossier, EventLog, dict[str, Any]]:
        """Load a detached, replay-verified current snapshot without touching `_logs`."""

        snapshot = self.load_run_snapshot(run_id)
        return snapshot.dossier, snapshot.event_log, snapshot.run_record_dict()

    def _validate_persisted_run_inputs(
        self,
        *,
        dossier: Dossier,
        log: EventLog,
        input_record: object,
        input_address: str,
    ) -> None:
        """Close the persisted event lineage over canonical manifest and RNA inputs."""

        source_receipt_max = self._persisted_source_receipt_max()
        if len(dossier.source_receipts) > source_receipt_max:
            raise ValidationError(
                "persisted source_receipts exceeds the configured maximum of "
                f"{source_receipt_max} items"
            )
        if type(input_record) is not dict:
            raise ValidationError("persisted manifest input must be an exact object")
        try:
            manifest = CaseManifest.from_dict(input_record)
        except Exception as exc:  # noqa: BLE001 - stored inputs fail closed
            raise ValidationError("persisted manifest input is not canonical") from exc
        if canonical_bytes(manifest.to_dict()) != canonical_bytes(input_record):
            raise ValidationError("persisted manifest input does not round-trip exactly")
        self._validate_manifest_contract(manifest, "persisted manifest input")

        events = log.all()
        case_events = tuple(event for event in events if event.event_type == "case_received")
        if (
            not events
            or len(case_events) != 1
            or case_events[0] is not events[0]
            or case_events[0].event_id != f"evt-{dossier.run_id}-received"
        ):
            raise ValidationError("persisted event log must begin with one canonical case receipt")
        payload = case_events[0].payload
        base_fields = {"input_address", "case_id"}
        rna_fields = {"rna_input_address", "rna_consequence_count"}
        fields = set(payload)
        if fields not in (base_fields, base_fields | rna_fields):
            raise ValidationError("persisted case receipt has a non-canonical payload shape")
        if (
            type(payload.get("input_address")) is not str
            or payload["input_address"] != input_address
            or type(payload.get("case_id")) is not str
            or payload["case_id"] != dossier.case_id
            or manifest.case_id != dossier.case_id
        ):
            raise ValidationError("persisted case receipt does not match its manifest and dossier")

        self._validate_persisted_review_events(dossier, log)

        rna_rows: tuple[RNAConsequenceEvidence, ...] = ()
        rna_address: str | None = None
        rna_source_bytes = 0
        if fields == base_fields | rna_fields:
            rna_address = payload["rna_input_address"]
            rna_count = payload["rna_consequence_count"]
            if type(rna_address) is not str:
                raise ValidationError("persisted RNA input address must be an exact string")
            if (
                type(rna_count) is not int
                or rna_count <= 0
                or rna_count > _MAX_RUNTIME_RNA_CONSEQUENCES
            ):
                raise ValidationError("persisted RNA input count is outside runtime limits")
            rna_read_max = min(
                self._rna_input_max_bytes,
                self._source_closure_max_bytes,
                self._persisted_object_max_bytes(),
            )
            try:
                rna_record = self.store.store.get_verified(
                    rna_address,
                    max_bytes=rna_read_max,
                )
            except StoreError as exc:
                if (
                    rna_read_max == self._source_closure_max_bytes
                    and "stored object exceeds" in str(exc)
                ):
                    raise ValidationError(
                        "persisted source closure exceeds its aggregate canonical byte ceiling"
                    ) from exc
                if "stored object exceeds" in str(exc):
                    raise ValidationError(
                        "persisted RNA input object exceeds its configured byte ceiling"
                    ) from exc
                raise ValidationError("persisted RNA input object is missing or invalid") from exc
            if type(rna_record) is not dict or set(rna_record) != {
                "schema_version",
                "kind",
                "consequences",
            }:
                raise ValidationError("persisted RNA input object has a non-canonical shape")
            rna_source_bytes = len(canonical_bytes(rna_record))
            if (
                rna_record["schema_version"] != "1.0.0"
                or rna_record["kind"] != "rna_consequence_batch"
                or type(rna_record["consequences"]) is not list
                or len(rna_record["consequences"]) != rna_count
            ):
                raise ValidationError("persisted RNA input object disagrees with its receipt")
            raw_rows = self._preflight_rna_input_rows(
                rna_record["consequences"],
                expected_count=rna_count,
            )
            try:
                rows = tuple(
                    validate_rna_consequence(RNAConsequenceEvidence.from_mapping(row))
                    for row in raw_rows
                )
            except Exception as exc:  # noqa: BLE001 - stored RNA rows fail closed
                raise ValidationError("persisted RNA input rows are not canonical") from exc
            if len(rows) != rna_count:
                raise ValidationError("persisted RNA input rows must be exact objects")
            expected_rows = tuple(sorted(rows, key=lambda row: row.content_address))
            if (
                len({row.content_address for row in rows}) != len(rows)
                or rows != expected_rows
                or canonical_bytes(rna_record["consequences"])
                != canonical_bytes([row.to_dict() for row in rows])
            ):
                raise ValidationError("persisted RNA input object is not canonical or addressed")
            rna_rows = rows

        rna_claims = tuple(
            claim for claim in dossier.evidence if claim.channel == RNA_CONSEQUENCE_CHANNEL
        )
        owner_references = tuple(
            claim for claim in dossier.evidence if "retained_owner_address" in claim.payload
        )
        if rna_address is None:
            if rna_claims or owner_references:
                raise ValidationError(
                    "persisted dossier contains RNA ownership without a recorded RNA input"
                )
        else:
            if rna_address not in dossier.source_bundle_addresses:
                raise ValidationError(
                    "persisted dossier does not declare its recorded RNA input owner"
                )
            if any(claim.channel != RNA_CONSEQUENCE_CHANNEL for claim in owner_references):
                raise ValidationError("retained RNA ownership appears on a non-RNA claim")
            recorded_rna_rows = {row.content_address: row for row in rna_rows}
            for claim in rna_claims:
                try:
                    rna_claim_public_projection(claim)
                    claimed_consequence = validate_rna_consequence(
                        RNAConsequenceEvidence.from_mapping(claim.payload["rna_consequence"])
                    )
                except Exception as exc:  # noqa: BLE001 - persisted claims fail closed
                    raise ValidationError("persisted RNA claim is not canonical") from exc
                if (
                    claim.depends_on != (rna_address,)
                    or claim.payload.get("retained_owner_address") != rna_address
                ):
                    raise ValidationError(
                        "persisted RNA claim is not bound to its recorded input owner"
                    )
                recorded_consequence = recorded_rna_rows.get(claimed_consequence.content_address)
                if (
                    recorded_consequence is None
                    or claimed_consequence.to_dict() != recorded_consequence.to_dict()
                ):
                    raise ValidationError(
                        "persisted RNA claim consequence is not present in its recorded input"
                    )

        self._validate_persisted_source_closure(
            manifest=manifest,
            dossier=dossier,
            events=events,
            rna_address=rna_address,
            initial_source_bytes=rna_source_bytes,
        )

        if self._run_id(manifest, rna_rows) != dossier.run_id:
            raise ValidationError("persisted inputs do not reproduce the run identifier")

    @staticmethod
    def _source_event_addresses(
        payload: Mapping[str, Any],
        field_name: str,
        label: str,
    ) -> tuple[str, ...]:
        raw = payload.get(field_name)
        if not isinstance(raw, list):
            raise ValidationError(f"{label} source addresses must be an exact array")
        values = tuple(_runtime_sha256_address(item, f"{label} source address") for item in raw)
        if len(values) != len(set(values)):
            raise ValidationError(f"{label} source addresses must be unique")
        return values

    @staticmethod
    def _persisted_reference_bundle_projection(
        records: Mapping[str, dict[str, Any]],
        addresses: tuple[str, ...],
        manifest: CaseManifest,
    ) -> tuple[
        tuple[ReferenceBundle, ...],
        tuple[CandidateElement, ...],
        tuple[dict[str, Any], ...],
        tuple[str, ...],
    ]:
        """Validate persisted reference bundle identities and reopen their elements."""

        if len(addresses) != len(manifest.variants):
            raise ValidationError(
                "persisted reference bundles must cover every manifest variant exactly once"
            )
        elements: list[CandidateElement] = []
        receipts: list[dict[str, Any]] = []
        warnings: list[str] = []
        bundles: list[ReferenceBundle] = []
        for address, variant in zip(addresses, manifest.variants, strict=True):
            try:
                raw = records[address]
            except KeyError as exc:
                raise ValidationError("persisted reference bundle is missing") from exc
            bundle = ReferenceBundle.from_dict(raw, manifest.context)
            if bundle.variant_id != variant.variant_id:
                raise ValidationError("persisted reference bundle variant identity is invalid")
            if bundle.context_key != manifest.context.key:
                raise ValidationError("persisted reference bundle context identity is invalid")
            bundles.append(bundle)
            elements.extend(bundle.elements)
            receipts.extend(receipt.to_dict() for receipt in bundle.receipts)
            warnings.extend(bundle.warnings)
        return tuple(bundles), tuple(elements), tuple(receipts), tuple(warnings)

    @staticmethod
    def _persisted_atlas_bundle_projection(
        records: Mapping[str, dict[str, Any]],
        replay_input_addresses: tuple[str, ...],
        bundle_addresses: tuple[str, ...],
        manifest: CaseManifest,
        reference_bundles: tuple[ReferenceBundle, ...],
    ) -> tuple[tuple[AtlasBundle, ...], tuple[dict[str, Any], ...], tuple[str, ...]]:
        """Reopen each replay input before its derived Atlas bundle."""

        if (
            len(replay_input_addresses) != len(bundle_addresses)
            or len(bundle_addresses) != len(manifest.variants)
            or len(reference_bundles) != len(manifest.variants)
        ):
            raise ValidationError(
                "persisted atlas replay-input/bundle pairs must cover every manifest variant "
                "exactly once"
            )
        bundles: list[AtlasBundle] = []
        receipts: list[dict[str, Any]] = []
        warnings: list[str] = []
        for replay_input_address, bundle_address, variant, reference_bundle in zip(
            replay_input_addresses,
            bundle_addresses,
            manifest.variants,
            reference_bundles,
            strict=True,
        ):
            try:
                replay_raw = records[replay_input_address]
            except KeyError as exc:
                raise ValidationError("persisted atlas replay inputs are missing") from exc
            if content_hash(replay_raw) != replay_input_address:
                raise ValidationError("persisted atlas replay-input source address is invalid")
            replay_inputs = AtlasReplayInputs.from_dict(
                replay_raw,
                variant,
                manifest.context,
                reference_bundle=reference_bundle,
            )
            if replay_inputs.reference_bundle_address != reference_bundle.content_address:
                raise ValidationError(
                    "persisted atlas replay inputs do not bind their exact reference bundle"
                )
            try:
                bundle_raw = records[bundle_address]
            except KeyError as exc:
                raise ValidationError("persisted atlas bundle is missing") from exc
            bundle = AtlasBundle.from_dict(
                bundle_raw,
                variant,
                manifest.context,
                reference_bundle=reference_bundle,
                replay_inputs=replay_inputs,
            )
            if content_hash(bundle_raw) != bundle_address:
                raise ValidationError("persisted atlas bundle source address is invalid")
            if (
                bundle.source_bundle_address != reference_bundle.content_address
                or bundle.replay_inputs_address != replay_inputs.content_address
                or bundle.query != replay_inputs.query
            ):
                raise ValidationError(
                    "persisted atlas bundle does not bind its exact replay and reference inputs"
                )
            bundles.append(bundle)
            receipts.extend(receipt.to_dict() for receipt in bundle.receipts)
            warnings.extend(bundle.warnings)
        return tuple(bundles), tuple(receipts), tuple(warnings)

    def _validate_persisted_source_closure(
        self,
        *,
        manifest: CaseManifest,
        dossier: Dossier,
        events: tuple[Any, ...],
        rna_address: str | None,
        initial_source_bytes: int = 0,
    ) -> None:
        """Require every declared source object and adapter derivation to replay exactly."""

        if (
            type(initial_source_bytes) is not int
            or not 0 <= initial_source_bytes <= self._source_closure_max_bytes
        ):
            raise ValidationError(
                "persisted source closure exceeds its aggregate canonical byte ceiling"
            )

        event_types = tuple(event.event_type for event in events)
        singleton_types = (
            "case_received",
            "hypotheses_built",
            "validation_routes_planned",
            "dossier_created",
        )
        if any(event_types.count(event_type) != 1 for event_type in singleton_types):
            raise ValidationError("persisted run lifecycle event cardinality is invalid")
        optional_source_types = (
            "public_reference_enriched",
            "public_atlas_collected",
            "adapter_evidence_collected",
        )
        if any(event_types.count(event_type) > 1 for event_type in optional_source_types):
            raise ValidationError("persisted run source event cardinality is invalid")
        if (
            "public_atlas_collected" in event_types
            and "public_reference_enriched" not in event_types
        ):
            raise ValidationError("persisted atlas event requires reference enrichment")
        expected_prefix = ["case_received"]
        expected_prefix.extend(
            event_type for event_type in optional_source_types if event_type in event_types
        )
        expected_prefix.extend(("hypotheses_built", "validation_routes_planned", "dossier_created"))
        if event_types[: len(expected_prefix)] != tuple(expected_prefix):
            raise ValidationError("persisted run lifecycle events are not canonically ordered")
        allowed_suffix_types = frozenset(
            {
                "snapshot_predecessor_bound",
                "review_assigned",
                "review_recorded",
            }
        )
        if any(
            event_type not in allowed_suffix_types
            for event_type in event_types[len(expected_prefix) :]
        ):
            raise ValidationError("persisted run lifecycle contains an unknown event type")

        core_events = {
            event_type: next(event for event in events if event.event_type == event_type)
            for event_type in singleton_types[1:]
        }
        built_event = core_events["hypotheses_built"]
        built_payload = built_event.payload
        built_warnings = built_payload.get("warnings")
        if (
            built_event.event_id != f"evt-{dossier.run_id}-built"
            or set(built_payload) != {"hypothesis_count", "claim_count", "warnings"}
            or type(built_payload.get("hypothesis_count")) is not int
            or built_payload.get("hypothesis_count") != len(dossier.hypotheses)
            or type(built_payload.get("claim_count")) is not int
            or built_payload.get("claim_count") != len(dossier.evidence)
            or not isinstance(built_warnings, list)
            or any(type(item) is not str for item in built_warnings)
            or tuple(built_warnings) != dossier.warnings
        ):
            raise ValidationError("persisted hypotheses-built event is inconsistent")
        planned_event = core_events["validation_routes_planned"]
        if (
            planned_event.event_id != f"evt-{dossier.run_id}-planned"
            or set(planned_event.payload) != {"experiment_count"}
            or type(planned_event.payload.get("experiment_count")) is not int
            or planned_event.payload.get("experiment_count") != len(dossier.experiments)
        ):
            raise ValidationError("persisted validation-planning event is inconsistent")
        dossier_event = core_events["dossier_created"]
        if (
            dossier_event.event_id != f"evt-{dossier.run_id}-dossier"
            or set(dossier_event.payload) != {"dossier_id"}
            or dossier_event.payload.get("dossier_id") != dossier.dossier_id
        ):
            raise ValidationError("persisted dossier-created event is inconsistent")

        declared: list[str] = []
        if rna_address is not None:
            declared.append(rna_address)
        event_specs = (
            ("public_reference_enriched", "bundle_addresses", "reference"),
            ("public_atlas_collected", "bundle_addresses", "atlas"),
            ("adapter_evidence_collected", "source_bundle_addresses", "adapter"),
        )
        selected_events: dict[str, Any] = {}
        for event_type, address_field, label in event_specs:
            matching = tuple(event for event in events if event.event_type == event_type)
            if len(matching) > 1:
                raise ValidationError(f"persisted run contains duplicate {label} source events")
            if not matching:
                continue
            event = matching[0]
            event_suffix = "adapters" if label == "adapter" else label
            expected_event_id = f"evt-{dossier.run_id}-{event_suffix}"
            if event.event_id != expected_event_id:
                raise ValidationError(f"persisted {label} source event identity is invalid")
            selected_events[event_type] = event
            if label == "reference":
                declared.append(
                    _runtime_sha256_address(
                        event.payload.get("submitted_input_address"),
                        "reference submitted input address",
                    )
                )
            if label == "atlas":
                replay_input_addresses = self._source_event_addresses(
                    event.payload,
                    "replay_input_addresses",
                    "atlas replay input",
                )
                bundle_addresses = self._source_event_addresses(
                    event.payload,
                    "bundle_addresses",
                    "atlas bundle",
                )
                if len(replay_input_addresses) != len(bundle_addresses):
                    raise ValidationError(
                        "persisted atlas replay-input and bundle address arrays must have "
                        "equal length"
                    )
                if set(replay_input_addresses) & set(bundle_addresses):
                    raise ValidationError(
                        "persisted atlas replay-input and bundle addresses must be disjoint"
                    )
                if len(bundle_addresses) != len(manifest.variants):
                    raise ValidationError(
                        "persisted atlas source address count is inconsistent"
                    )
                declared.extend(
                    address
                    for pair in zip(replay_input_addresses, bundle_addresses, strict=True)
                    for address in pair
                )
                continue
            stage_addresses = self._source_event_addresses(
                event.payload,
                address_field,
                label,
            )
            expected_count = (
                len(manifest.variants)
                if label == "reference"
                else len(_ADAPTER_INPUT_VERSION_KEYS)
            )
            if len(stage_addresses) != expected_count:
                raise ValidationError(f"persisted {label} source address count is inconsistent")
            declared.extend(stage_addresses)
        # One immutable object can legitimately serve two adjacent stages (for
        # example, a no-op reference manifest is also the adapter base).  The
        # dossier stores the ordered unique closure while each event retains its
        # complete stage-local declaration.
        if tuple(dict.fromkeys(declared)) != dossier.source_bundle_addresses:
            raise ValidationError(
                "persisted dossier source bundle declarations do not match its event lineage"
            )

        retained_source_bytes = initial_source_bytes
        records: dict[str, dict[str, Any]] = {}
        for address in dossier.source_bundle_addresses:
            if address == rna_address:
                continue
            remaining_bytes = self._source_closure_max_bytes - retained_source_bytes
            if remaining_bytes <= 0:
                raise ValidationError(
                    "persisted source closure exceeds its aggregate canonical byte ceiling"
                )
            try:
                raw = self.store.store.get_verified(
                    address,
                    max_bytes=min(self._persisted_object_max_bytes(), remaining_bytes),
                )
            except StoreError as exc:
                if (
                    remaining_bytes < self._persisted_object_max_bytes()
                    and "stored object exceeds" in str(exc)
                ):
                    raise ValidationError(
                        "persisted source closure exceeds its aggregate canonical byte ceiling"
                    ) from exc
                raise ValidationError(
                    f"persisted source object is missing or invalid: {address}"
                ) from exc
            if type(raw) is not dict:
                raise ValidationError("persisted source objects must be exact JSON objects")
            retained_source_bytes += len(canonical_bytes(raw))
            if retained_source_bytes > self._source_closure_max_bytes:
                raise ValidationError(
                    "persisted source closure exceeds its aggregate canonical byte ceiling"
                )
            records[address] = raw

        reference_event = selected_events.get("public_reference_enriched")
        atlas_event = selected_events.get("public_atlas_collected")
        adapter_event = selected_events.get("adapter_evidence_collected")
        reference_manifest: CaseManifest | None = None
        reference_bundles: tuple[ReferenceBundle, ...] = ()
        expected_source_receipts: tuple[dict[str, Any], ...] = ()
        if reference_event is not None:
            if set(reference_event.payload) != _REFERENCE_EVENT_FIELDS:
                raise ValidationError("persisted reference event has a non-canonical payload shape")
            submitted_reference_address = _runtime_sha256_address(
                reference_event.payload.get("submitted_input_address"),
                "reference submitted input address",
            )
            effective_reference_address = _runtime_sha256_address(
                reference_event.payload.get("effective_input_address"),
                "reference effective input address",
            )
            expected_reference_effective = (
                adapter_event.payload.get("base_input_address")
                if adapter_event is not None
                else manifest.content_address
            )
            if effective_reference_address != expected_reference_effective:
                raise ValidationError(
                    "persisted reference enrichment does not bind the adapter base manifest"
                )
            try:
                submitted_record = records[submitted_reference_address]
                submitted_manifest = CaseManifest.from_dict(submitted_record)
                effective_record = (
                    records[effective_reference_address]
                    if adapter_event is not None
                    else manifest.to_dict()
                )
                reference_manifest = CaseManifest.from_dict(effective_record)
            except (KeyError, TypeError, ValueError) as exc:
                raise ValidationError("persisted reference manifest transition is invalid") from exc
            if (
                canonical_bytes(submitted_manifest.to_dict()) != canonical_bytes(submitted_record)
                or canonical_bytes(reference_manifest.to_dict())
                != canonical_bytes(effective_record)
                or submitted_manifest.content_address != submitted_reference_address
                or reference_manifest.content_address != effective_reference_address
            ):
                raise ValidationError("persisted reference manifests do not round-trip exactly")
            reference_addresses = self._source_event_addresses(
                reference_event.payload,
                "bundle_addresses",
                "reference",
            )
            reference_bundles, source_elements, reference_receipts, bundle_warnings = (
                self._persisted_reference_bundle_projection(
                    records,
                    reference_addresses,
                    reference_manifest,
                )
            )
            self._validate_reference_enrichment_transition(
                submitted_manifest,
                reference_manifest,
                source_elements,
            )
            receipt_count = reference_event.payload.get("receipt_count")
            event_warnings = reference_event.payload.get("warnings")
            if type(receipt_count) is not int or receipt_count != len(reference_receipts):
                raise ValidationError("persisted reference receipt count is invalid")
            if (
                not isinstance(event_warnings, list)
                or any(type(item) is not str for item in event_warnings)
                or len(event_warnings) != len(set(event_warnings))
                or not set(bundle_warnings).issubset(event_warnings)
                or not set(event_warnings).issubset(dossier.warnings)
            ):
                raise ValidationError("persisted reference warnings are invalid")
            if tuple(dossier.source_receipts[:receipt_count]) != reference_receipts:
                raise ValidationError(
                    "persisted reference receipts do not match the dossier source prefix"
                )
            expected_source_receipts = reference_receipts

        expected_atlas_claims: tuple[EvidenceClaim, ...] = ()
        if atlas_event is not None:
            if set(atlas_event.payload) != _ATLAS_EVENT_FIELDS:
                raise ValidationError("persisted atlas event has a non-canonical payload shape")
            if reference_manifest is None or not reference_bundles:
                raise ValidationError("persisted atlas closure requires reference bundles")
            atlas_replay_input_addresses = self._source_event_addresses(
                atlas_event.payload,
                "replay_input_addresses",
                "atlas replay input",
            )
            atlas_bundle_addresses = self._source_event_addresses(
                atlas_event.payload,
                "bundle_addresses",
                "atlas bundle",
            )
            if len(atlas_replay_input_addresses) != len(atlas_bundle_addresses):
                raise ValidationError(
                    "persisted atlas replay-input and bundle address arrays must have equal length"
                )
            if set(atlas_replay_input_addresses) & set(atlas_bundle_addresses):
                raise ValidationError(
                    "persisted atlas replay-input and bundle addresses must be disjoint"
                )
            atlas_bundles, atlas_receipts, atlas_bundle_warnings = (
                self._persisted_atlas_bundle_projection(
                    records,
                    atlas_replay_input_addresses,
                    atlas_bundle_addresses,
                    reference_manifest,
                    reference_bundles,
                )
            )
            expected_atlas_claims, atlas_link_warnings = self._link_atlas_claims(
                reference_manifest,
                atlas_bundles,
            )
            expected_atlas_warnings = tuple(
                dict.fromkeys(atlas_bundle_warnings + atlas_link_warnings)
            )
            event_claim_count = atlas_event.payload.get("claim_count")
            event_warnings = atlas_event.payload.get("warnings")
            if type(event_claim_count) is not int or event_claim_count != len(
                expected_atlas_claims
            ):
                raise ValidationError("persisted atlas claim count is invalid")
            if (
                not isinstance(event_warnings, list)
                or any(type(item) is not str for item in event_warnings)
                or tuple(event_warnings) != expected_atlas_warnings
                or not set(event_warnings).issubset(dossier.warnings)
            ):
                raise ValidationError("persisted atlas warnings are invalid")
            expected_source_receipts += atlas_receipts

        actual_atlas_claims = tuple(
            claim for claim in dossier.evidence if claim.produced_by == "public_atlas_retriever"
        )
        actual_atlas_by_id = {
            claim.evidence_id: canonical_bytes(claim.to_dict()) for claim in actual_atlas_claims
        }
        expected_atlas_by_id = {
            claim.evidence_id: canonical_bytes(claim.to_dict()) for claim in expected_atlas_claims
        }
        if actual_atlas_by_id != expected_atlas_by_id:
            raise ValidationError(
                "persisted atlas claims do not match their retained source bundles"
            )
        dossier_edge_claim_ids = {
            claim_id
            for hypothesis in dossier.hypotheses
            for edge in hypothesis.edges
            for claim_id in edge.claim_ids
        }
        if any(claim.evidence_id not in dossier_edge_claim_ids for claim in expected_atlas_claims):
            raise ValidationError(
                "persisted atlas claim is absent from the dossier hypothesis graph"
            )
        if canonical_bytes(tuple(dossier.source_receipts)) != canonical_bytes(
            expected_source_receipts
        ):
            raise ValidationError(
                "persisted dossier source receipts do not match its source events"
            )

        has_adapter_versions = any(
            key in manifest.input_versions for key in _ADAPTER_INPUT_VERSION_KEYS
        )
        if adapter_event is None:
            if has_adapter_versions:
                raise ValidationError(
                    "persisted manifest declares adapter inputs without an adapter event"
                )
            return
        if not has_adapter_versions:
            raise ValidationError("persisted adapter event is absent from manifest identity")
        adapter_claim_count = self._validate_persisted_adapter_closure(
            manifest=manifest,
            dossier=dossier,
            event=adapter_event,
            records=records,
            remaining_claims=(self.builder.limits.max_external_claims - len(expected_atlas_claims)),
        )
        if adapter_claim_count > (
            self.builder.limits.max_external_claims - len(expected_atlas_claims)
        ):
            raise ValidationError(
                "external_claims exceeds the configured maximum of "
                f"{self.builder.limits.max_external_claims} items"
            )

    def _validate_persisted_adapter_closure(
        self,
        *,
        manifest: CaseManifest,
        dossier: Dossier,
        event: Any,
        records: Mapping[str, dict[str, Any]],
        remaining_claims: int,
    ) -> int:
        if type(remaining_claims) is not int or remaining_claims < 0:
            raise ValidationError("persisted adapter claim allowance is invalid")
        payload = event.payload
        if set(payload) != _ADAPTER_EVENT_FIELDS:
            raise ValidationError("persisted adapter event has a non-canonical payload shape")
        source_addresses = self._source_event_addresses(
            payload,
            "source_bundle_addresses",
            "adapter",
        )
        if len(source_addresses) != len(_ADAPTER_INPUT_VERSION_KEYS):
            raise ValidationError("persisted adapter source closure is incomplete")
        base_address, registry_address, resolution_address, claims_address = source_addresses
        expected_version_addresses = dict(
            zip(_ADAPTER_INPUT_VERSION_KEYS, source_addresses, strict=True)
        )
        if any(
            manifest.input_versions.get(key) != address
            for key, address in expected_version_addresses.items()
        ):
            raise ValidationError("persisted adapter sources are not bound into manifest identity")
        scalar_addresses = (
            ("base_input_address", base_address),
            ("effective_input_address", manifest.content_address),
            ("registry_bundle_address", registry_address),
            ("resolution_bundle_address", resolution_address),
            ("claim_collection_bundle_address", claims_address),
        )
        if any(payload.get(field) != expected for field, expected in scalar_addresses):
            raise ValidationError("persisted adapter event source addresses are inconsistent")
        try:
            base_record = records[base_address]
            registry_record = records[registry_address]
            resolution_record = records[resolution_address]
            claims_record = records[claims_address]
            raw_attributions = claims_record.get("attributions")
            if type(raw_attributions) is not list:
                raise ValidationError("persisted adapter claim attributions must be an exact array")
            if len(raw_attributions) > 100_000:
                raise ValidationError(
                    "persisted adapter claim attributions exceed their hard item ceiling"
                )
            raw_claim_count = 0
            for attribution in raw_attributions:
                if type(attribution) is not dict or type(attribution.get("claims")) is not list:
                    raise ValidationError(
                        "persisted adapter claim attribution is not an exact object"
                    )
                attribution_claim_count = len(attribution["claims"])
                if attribution_claim_count > remaining_claims - raw_claim_count:
                    raise ValidationError(
                        "external_claims exceeds the configured maximum of "
                        f"{self.builder.limits.max_external_claims} items"
                    )
                raw_claim_count += attribution_claim_count
            base_manifest = CaseManifest.from_dict(base_record)
            registry_snapshot = AdapterRegistrySnapshot.from_dict(registry_record)
            resolution = AdapterResolutionReport.from_dict(resolution_record)
            claim_report = AdapterClaimCollectionReport.from_dict(claims_record)
        except (KeyError, TypeError, ValueError) as exc:
            raise ValidationError("persisted adapter source records are invalid") from exc
        typed_records = (
            (base_manifest.to_dict(), base_record),
            (registry_snapshot.to_dict(), registry_record),
            (resolution.to_dict(), resolution_record),
            (claim_report.to_dict(), claims_record),
        )
        if any(canonical_bytes(typed) != canonical_bytes(raw) for typed, raw in typed_records):
            raise ValidationError("persisted adapter source records do not round-trip exactly")
        adapter_ids = payload.get("adapter_ids")
        if not isinstance(adapter_ids, list) or any(type(item) is not str for item in adapter_ids):
            raise ValidationError("persisted adapter event adapter_ids must be an exact array")
        if (
            tuple(adapter_ids) != resolution.adapter_ids
            or claim_report.adapter_ids != resolution.adapter_ids
            or resolution.manifest_address != base_address
            or claim_report.manifest_address != base_address
            or resolution.registry_address != registry_snapshot.content_address
            or claim_report.registry_snapshot != registry_snapshot
            or claim_report.registry_address != resolution.registry_address
            or claim_report.resolution_address != resolution.content_address
            or payload.get("registry_address") != resolution.registry_address
            or payload.get("resolution_address") != resolution.content_address
            or payload.get("claim_collection_address") != claim_report.content_address
        ):
            raise ValidationError("persisted adapter reports do not form one provenance closure")
        resolution.validate_manifest(base_manifest)
        claim_report.validate_claim_ownership(resolution)
        counters = (
            ("resolved_element_count", resolution.element_count),
            ("attribution_count", claim_report.attribution_count),
            ("claim_count", claim_report.claim_count),
        )
        if any(type(payload.get(field)) is not int for field, _expected in counters) or any(
            payload.get(field) != expected for field, expected in counters
        ):
            raise ValidationError("persisted adapter event counters are inconsistent")
        expected_manifest = self._materialize_adapter_manifest(
            base_manifest,
            resolution,
            source_addresses,
        )
        if canonical_bytes(expected_manifest.to_dict()) != canonical_bytes(manifest.to_dict()):
            raise ValidationError("persisted adapter resolution does not reproduce the manifest")
        evidence_by_id = {claim.evidence_id: claim for claim in dossier.evidence}
        edge_claims = {
            claim_id
            for hypothesis in dossier.hypotheses
            for edge in hypothesis.edges
            for claim_id in edge.claim_ids
        }
        for claim in claim_report.claims:
            persisted = evidence_by_id.get(claim.evidence_id)
            if (
                persisted is None
                or canonical_bytes(persisted.to_dict()) != canonical_bytes(claim.to_dict())
                or claim.evidence_id not in edge_claims
            ):
                raise ValidationError(
                    "persisted adapter claim is absent from the dossier hypothesis graph"
                )
        selected_adapter_ids = frozenset(claim_report.adapter_ids)
        dossier_adapter_claims = tuple(
            claim for claim in dossier.evidence if claim.produced_by in selected_adapter_ids
        )
        if len(dossier_adapter_claims) != claim_report.claim_count:
            raise ValidationError(
                "persisted dossier adapter claims do not exactly match claim collection"
            )
        reported_claims = {claim.evidence_id: claim for claim in claim_report.claims}
        if any(
            (reported := reported_claims.get(claim.evidence_id)) is None
            or canonical_bytes(reported.to_dict()) != canonical_bytes(claim.to_dict())
            for claim in dossier_adapter_claims
        ):
            raise ValidationError(
                "persisted dossier adapter claims do not exactly match claim collection"
            )
        return claim_report.claim_count

    @staticmethod
    def _preflight_rna_input_row(
        row: object,
        *,
        index: int,
    ) -> tuple[dict[str, Any], bytes]:
        """Validate and encode one RNA closure row before retaining another row."""

        if type(index) is not int or index < 0 or index >= _MAX_RUNTIME_RNA_CONSEQUENCES:
            raise ValidationError("RNA input row index is outside its bounded range")
        if type(row) is not dict:
            raise ValidationError(f"RNA input row {index} must be an exact object")
        if set(row) != _RNA_CONSEQUENCE_RECORD_FIELDS:
            raise ValidationError(f"RNA input row {index} has a non-canonical shape")
        reason_codes = row.get("reason_codes")
        if type(reason_codes) is not list or len(reason_codes) > _MAX_RUNTIME_RNA_REASON_CODES:
            raise ValidationError(
                f"RNA input row {index} reason_codes exceeds its collection limit"
            )
        if any(
            type(code) is not str or not code or len(code) > _MAX_RUNTIME_RNA_REASON_CODE_CHARACTERS
            for code in reason_codes
        ):
            raise ValidationError(
                f"RNA input row {index} reason_codes must be bounded exact strings"
            )
        try:
            encoded = canonical_bytes(row)
        except (OverflowError, RecursionError, TypeError, UnicodeError, ValueError) as exc:
            raise ValidationError(f"RNA input row {index} is not canonical JSON") from exc
        if len(encoded) > _MAX_RUNTIME_RNA_ROW_BYTES:
            raise ValidationError(
                f"RNA input row {index} exceeds {_MAX_RUNTIME_RNA_ROW_BYTES} bytes"
            )
        return row, encoded

    @classmethod
    def _preflight_rna_input_rows(
        cls,
        raw_rows: object,
        *,
        expected_count: int,
    ) -> list[dict[str, Any]]:
        """Bound nested RNA collections before typed hydration can allocate from them."""

        if (
            type(expected_count) is not int
            or expected_count <= 0
            or expected_count > _MAX_RUNTIME_RNA_CONSEQUENCES
            or type(raw_rows) is not list
            or len(raw_rows) != expected_count
        ):
            raise ValidationError("RNA input rows disagree with the bounded expected count")
        checked: list[dict[str, Any]] = []
        for index, row in enumerate(raw_rows):
            checked_row, _encoded = cls._preflight_rna_input_row(row, index=index)
            checked.append(checked_row)
        return checked

    @staticmethod
    def _dossier_reuse_projection(dossier: Dossier) -> dict[str, Any]:
        """Project scientific output while omitting only runtime-generated identity fields."""

        projection = dossier.to_dict()
        if type(projection) is not dict:
            raise ValidationError("dossier reuse projection must be an exact object")
        try:
            for field_name in ("created_at", "event_head", "content_address"):
                projection.pop(field_name)
            evidence = projection["evidence"]
            if type(evidence) is not list:
                raise TypeError("dossier evidence projection must be an array")
            for claim in evidence:
                if type(claim) is not dict:
                    raise TypeError("dossier evidence projection entries must be objects")
                claim.pop("created_at")
        except (KeyError, TypeError) as exc:
            raise ValidationError("dossier reuse projection is malformed") from exc
        return projection

    @staticmethod
    def _event_reuse_projection(log: EventLog) -> dict[str, Any]:
        """Project event semantics while omitting timestamps and their hash links."""

        record = log.to_record()
        if type(record) is not dict or set(record) != {"run_id", "events"}:
            raise ValidationError("event reuse projection must be an exact record")
        rows = record["events"]
        if type(rows) is not list:
            raise ValidationError("event reuse projection events must be an exact array")
        events: list[dict[str, Any]] = []
        try:
            for row in rows:
                if type(row) is not dict:
                    raise TypeError("event reuse projection entries must be objects")
                projected = dict(row)
                for field_name in ("created_at", "previous_hash", "event_hash"):
                    projected.pop(field_name)
                events.append(projected)
        except (KeyError, TypeError) as exc:
            raise ValidationError("event reuse projection is malformed") from exc
        return {"run_id": record["run_id"], "events": events}

    def _reuse_untouched_offline_draft(
        self,
        candidate: Dossier,
        candidate_log: EventLog,
    ) -> Dossier | None:
        """Reuse only a replay-valid, never-advanced equivalent offline draft."""

        run_path = self.store.runs / f"{candidate.run_id}.json"
        if not run_path.exists():
            return None

        persisted, persisted_log, run_record = self._load_current_snapshot(candidate.run_id)
        event_history = run_record.get("event_history")
        dossier_history = run_record.get("dossier_history")
        untouched = (
            type(event_history) is list
            and event_history == [run_record["event_address"]]
            and type(dossier_history) is list
            and dossier_history == [run_record["dossier_address"]]
            and persisted.status is ResearchStatus.REVIEW_REQUIRED
            and persisted.review is None
            and not any(
                event.event_type in {"review_assigned", "review_recorded"}
                for event in persisted_log.all()
            )
        )
        equivalent = untouched and canonical_bytes(
            self._dossier_reuse_projection(candidate)
        ) == canonical_bytes(self._dossier_reuse_projection(persisted))
        equivalent = equivalent and canonical_bytes(
            self._event_reuse_projection(candidate_log)
        ) == canonical_bytes(self._event_reuse_projection(persisted_log))
        if not equivalent:
            conflict = StoreError(f"run already exists: {candidate.run_id}")
            raise ValidationError(f"run publication failed: {conflict}") from conflict

        self._logs[candidate.run_id] = persisted_log
        return persisted

    @staticmethod
    def _require_valid(report: ValidationReport, label: str) -> None:
        """Raise one bounded deterministic error for an invalid validation report."""

        if type(report) is not ValidationReport:
            raise ValidationError(f"{label} returned a non-canonical validation report")
        try:
            checked = ValidationReport(report.valid, report.issues)
            canonical_issues = tuple(
                ValidationIssue(
                    issue.code,
                    issue.severity,
                    issue.message,
                    issue.path,
                    issue.remediation,
                )
                for issue in checked.issues
            )
            canonical = ValidationReport(checked.valid, canonical_issues)
        except Exception as exc:  # noqa: BLE001 - mutated reports fail closed
            raise ValidationError(f"{label} returned an invalid validation report") from exc
        if canonical.valid:
            return
        displayed = canonical.issues[:16]
        details = "; ".join(f"{issue.path}: {issue.code}" for issue in displayed)
        if len(canonical.issues) > len(displayed):
            details += f"; and {len(canonical.issues) - len(displayed)} more issue(s)"
        raise ValidationError(f"{label} failed contract validation: {details}")

    def _validate_manifest_contract(self, manifest: CaseManifest, label: str) -> None:
        validator = self._require_exact_validator(self.validator, "runtime validator")
        try:
            report = validator.validate_manifest(manifest)
        except Exception as exc:  # noqa: BLE001 - replaced dependencies fail closed
            raise ValidationError(f"{label} validation failed safely") from exc
        self._require_valid(report, label)

    def _validate_dossier_contract(self, dossier: Dossier, label: str) -> None:
        validator = self._require_exact_validator(self.validator, "runtime validator")
        try:
            report = validator.validate_dossier(dossier)
        except Exception as exc:  # noqa: BLE001 - replaced dependencies fail closed
            raise ValidationError(f"{label} validation failed safely") from exc
        self._require_valid(report, label)

    @staticmethod
    def _require_exact_validator(
        validator: object,
        label: str,
    ) -> ContractValidator:
        if type(validator) is not ContractValidator:
            raise ValidationError(f"{label} must be an exact ContractValidator")
        try:
            state = vars(validator)
            if type(state) is not dict or set(state) != {"limits"}:
                raise ValidationError(f"{label} has non-canonical instance state")
            canonical = ContractValidator(limits=validator.limits)
            if canonical.limits != validator.limits:
                raise ValidationError(f"{label} limits are not canonical")
        except Exception as exc:  # noqa: BLE001 - forged exact instances fail closed
            if isinstance(exc, ValidationError):
                raise
            raise ValidationError(f"{label} is mutated or invalid") from exc
        return validator

    def _check_release(self, dossier: Dossier, label: str) -> None:
        self._require_exact_policy()
        if type(self.release_gate) is not ReleaseGate:
            raise ValidationError("runtime release_gate must be an exact ReleaseGate")
        try:
            state = vars(self.release_gate)
            if type(state) is not dict or set(state) != {"policy", "validator"}:
                raise ValidationError("runtime release_gate has non-canonical instance state")
            if self.release_gate.policy is not self.policy:
                raise ValidationError("runtime release_gate is not bound to the runtime policy")
            self._require_exact_validator(
                self.release_gate.validator,
                "runtime release_gate validator",
            )
        except Exception as exc:  # noqa: BLE001 - forged exact instances fail closed
            if isinstance(exc, ValidationError):
                raise
            raise ValidationError("runtime release_gate is mutated or invalid") from exc
        try:
            report = self.release_gate.check(dossier)
        except Exception as exc:  # noqa: BLE001 - replaced dependencies fail closed
            raise ValidationError(f"{label} evaluation failed safely") from exc
        self._require_valid(report, label)

    def _require_exact_policy(self) -> None:
        if type(self.policy) is not ResearchPolicy:
            raise ValidationError("runtime policy must be an exact ResearchPolicy")
        try:
            state = vars(self.policy)
            if type(state) is not dict or set(state) != {"limits"}:
                raise ValidationError("runtime policy has non-canonical instance state")
            canonical = ResearchPolicy(limits=self.policy.limits)
            if canonical.limits != self.policy.limits:
                raise ValidationError("runtime policy limits are not canonical")
            if (
                type(self.release_gate) is ReleaseGate
                and self.release_gate.policy is not self.policy
            ):
                raise ValidationError("runtime policy was replaced after release gate construction")
        except Exception as exc:  # noqa: BLE001 - forged exact policy instances fail closed
            if isinstance(exc, ValidationError):
                raise
            raise ValidationError("runtime policy is mutated or invalid") from exc

    @staticmethod
    def _require_policy_decision(decision: PolicyDecision, label: str) -> PolicyDecision:
        if type(decision) is not PolicyDecision:
            raise ValidationError(f"{label} returned a non-canonical policy decision")
        try:
            raw = decision.to_dict()
            canonical = PolicyDecision(
                decision.allowed,
                decision.policy_version,
                decision.violations,
                decision.warnings,
            )
            if canonical.to_dict() != raw:
                raise ValidationError("policy decision does not round-trip exactly")
        except Exception as exc:  # noqa: BLE001 - mutated decisions fail closed
            raise ValidationError(f"{label} returned an invalid policy decision") from exc
        return canonical

    def _enforce_policy_texts(self, texts: Iterable[str], label: str) -> PolicyDecision:
        self._require_exact_policy()
        try:
            decision = self.policy.inspect_texts(texts)
        except Exception as exc:  # noqa: BLE001 - mutated policies fail closed
            raise ValidationError(f"{label} policy evaluation failed safely") from exc
        canonical = self._require_policy_decision(decision, label)
        if not canonical.allowed:
            raise PolicyViolation("; ".join(canonical.violations))
        return canonical

    def _policy_dossier_decision(self, dossier: Dossier, label: str) -> PolicyDecision:
        self._require_exact_policy()
        try:
            decision = self.policy.validate_dossier(dossier)
        except Exception as exc:  # noqa: BLE001 - mutated policies fail closed
            raise ValidationError(f"{label} policy evaluation failed safely") from exc
        return self._require_policy_decision(decision, label)

    def assign_review(
        self,
        run_id: str,
        *,
        assignment_id: str,
        reviewer: str,
        queue_id: str = "default-review",
        due_at: str | None = None,
        note: str = "",
    ) -> dict[str, Any]:
        """Append a durable reviewer assignment and create a new snapshot.

        Assignment is operational metadata, but it is still part of the
        replayable event chain.  The dossier is re-addressed with the new event
        head so the current run pointer and snapshot history remain coherent.
        """

        resolved_due_at = "" if due_at is None else due_at
        fields = {
            "run_id": run_id,
            "assignment_id": assignment_id,
            "reviewer": reviewer,
            "queue_id": queue_id,
            "due_at": resolved_due_at,
            "note": note,
        }
        if any(type(value) is not str for value in fields.values()):
            raise ValidationError("review assignment fields must be exact strings")
        for name in ("run_id", "assignment_id", "reviewer", "queue_id"):
            value = fields[name]
            if not value.strip():
                raise ValidationError(f"{name} must not be empty")
        if any(char in assignment_id for char in ("/", "\\", "..")):
            raise ValidationError("assignment_id contains an unsafe path fragment")
        self._enforce_policy_texts(tuple(fields.values()), "review assignment")
        dossier, log, run_record = self._load_current_snapshot(run_id)
        if dossier.review is not None and dossier.review.state in {
            ReviewState.ACCEPTED,
            ReviewState.REJECTED,
        }:
            raise ValidationError("cannot assign a completed review")
        if any(event.event_id == assignment_id for event in log.all()):
            raise ValidationError("assignment_id already exists in the run event chain")
        self._append_snapshot_predecessor_binding(log, run_record)
        assignment_body = {
            "assignment_id": assignment_id,
            "run_id": run_id,
            "case_id": dossier.case_id,
            "reviewer": reviewer,
            "queue_id": queue_id,
            "due_at": resolved_due_at,
            "note": note,
            "created_at": utc_now().isoformat(),
        }
        assignment = dict(assignment_body)
        assignment["content_address"] = content_hash(
            assignment_body,
            prefix="review-assignment",
        )
        log.append(
            "review_assigned",
            assignment,
            event_id=assignment_id,
        )
        updated = self._readdress(replace(dossier, event_head=log.head))
        self._validate_dossier_contract(updated, "assigned dossier")
        event_address, _ = self._persist(
            None,
            log,
            updated,
            dossier.input_address,
            expected_run=run_record,
        )
        self._logs[run_id] = log
        response_body = {
            "assignment": assignment,
            "dossier": updated.to_dict(),
            "event_address": event_address,
            "accepted": True,
        }
        return response_body | {
            "content_address": content_hash(response_body, prefix="review-assignment-response")
        }

    def get_run(self, run_id: str) -> dict[str, Any]:
        """Read the run index without rehydrating mutable objects."""

        return self.store.get_run(run_id)

    def get_dossier(self, dossier_address: str) -> dict[str, Any]:
        """Read an immutable dossier by its content address."""

        return self.load_dossier(dossier_address).to_dict()

    @staticmethod
    def _run_id(
        manifest: CaseManifest,
        rna_consequences: tuple[RNAConsequenceEvidence, ...] = (),
    ) -> str:
        payload: dict[str, Any] = {
            "input": manifest.content_address,
            "requested_by": manifest.requested_by,
        }
        if rna_consequences:
            payload["rna_consequences"] = sorted(item.content_address for item in rna_consequences)
        digest = content_hash(payload).split(":", 1)[1]
        return f"run-{digest[:24]}"

    @staticmethod
    def _dossier_address(dossier: Dossier) -> str:
        payload = {
            key: value for key, value in dossier.to_dict().items() if key != "content_address"
        }
        return content_hash(payload)

    def _make_dossier(
        self,
        *,
        manifest: CaseManifest | None,
        run_id: str,
        input_address: str,
        hypotheses: Iterable[Hypothesis],
        claims: Iterable[EvidenceClaim],
        experiments: Iterable[ExperimentOption],
        review: ReviewDecision | None,
        status: ResearchStatus,
        event_head: str,
        warnings: Iterable[str],
        case_id: str | None = None,
        created_at: str | None = None,
        source_receipts: tuple[Mapping[str, Any], ...] = (),
        source_bundle_addresses: tuple[str, ...] = (),
    ) -> Dossier:
        resolved_case_id = case_id
        if resolved_case_id is None:
            if manifest is None:
                raise ValidationError("manifest or case_id is required to build a dossier")
            resolved_case_id = manifest.case_id
        draft = Dossier(
            dossier_id=f"dos-{run_id}",
            case_id=resolved_case_id,
            run_id=run_id,
            created_at=created_at or utc_now().isoformat(),
            input_address=input_address,
            hypotheses=tuple(hypotheses),
            evidence=tuple(claims),
            experiments=tuple(experiments),
            review=review,
            research_use_only=True,
            policy_version=self.policy.version,
            event_head=event_head,
            content_address="pending",
            status=status,
            warnings=tuple(warnings),
            source_receipts=tuple(source_receipts),
            source_bundle_addresses=tuple(source_bundle_addresses),
        )
        return self._readdress(draft)

    def _readdress(self, dossier: Dossier) -> Dossier:
        pending = replace(dossier, content_address="pending")
        return replace(pending, content_address=self._dossier_address(pending))

    def _persist(
        self,
        manifest: CaseManifest | None,
        log: EventLog,
        dossier: Dossier,
        input_address: str,
        *,
        expected_run: dict[str, Any] | None = None,
    ) -> tuple[str, str]:
        if type(log) is not EventLog or not log.verify():
            raise ValidationError("cannot persist an invalid event log")
        if log.run_id != dossier.run_id:
            raise ValidationError("dossier run_id does not match the event log")
        if dossier.event_head != log.head:
            raise ValidationError("dossier event_head does not match the event log")
        if dossier.input_address != input_address:
            raise ValidationError("dossier input_address does not match the run input")
        if expected_run is not None and expected_run.get("input_address") != input_address:
            raise ValidationError("expected run input_address does not match the dossier")
        self._validate_dossier_contract(dossier, "persisted dossier")
        if dossier.status is ResearchStatus.RELEASED_RESEARCH:
            self._check_release(dossier, "release gate")
        try:
            event_address = self.store.store.put(log.to_record())
            dossier_address = self.store.store.put_at(dossier.content_address, dossier.to_dict())
            if expected_run is None:
                self.store.create_run(
                    log.run_id,
                    input_address=input_address,
                    event_address=event_address,
                    dossier_address=dossier_address,
                )
            else:
                self.store.advance_run(
                    log.run_id,
                    expected_run=expected_run,
                    event_address=event_address,
                    dossier_address=dossier_address,
                )
        except StoreError as exc:
            raise ValidationError(f"run publication failed: {exc}") from exc
        return event_address, dossier_address
