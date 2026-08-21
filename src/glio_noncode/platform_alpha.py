"""External-alpha typed runtime and quality-control contracts.

Domain 16 external-alpha adds four operational records around the typed
runtime: an append-only execution ledger, a versioned model registry, a
versioned data/reference registry, and a drift/out-of-domain monitor.  These
records are deliberately declarative and inspectable.  The ledger records
what a controlled execution reported; the registries resolve declared
compatibility; the monitor emits thresholded review signals.  None of these
surfaces turns a runtime event into a scientific, clinical, or treatment
conclusion.

All inputs retain exact context, source IDs, content addresses, and policy
boundaries.  Unknown transitions, missing artifacts, incompatible contracts,
invalid checksums, and out-of-domain observations are explicit states rather
than silently repaired values.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from math import isfinite, log
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty


class RuntimeAlphaState(StrEnum):
    """State shared by runtime, registry, and monitoring artifacts."""

    READY_FOR_REVIEW = "ready_for_review"
    PARTIAL = "partial"
    REVIEW_REQUIRED = "review_required"
    BLOCKED = "blocked"
    OUT_OF_DOMAIN = "out_of_domain"
    ABSTAINED = "abstained"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"
    COMPATIBLE = "compatible"
    DRIFT = "drift"
    WATCH = "watch"


class ExecutionEventKind(StrEnum):
    """Allowed append-only execution ledger events."""

    REQUESTED = "requested"
    PLANNED = "planned"
    ADMITTED = "admitted"
    STARTED = "started"
    CHECKPOINT = "checkpoint"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class ModelStatus(StrEnum):
    """Declared model registry lifecycle."""

    CANDIDATE = "candidate"
    VALIDATED = "validated"
    DEPRECATED = "deprecated"
    BLOCKED = "blocked"


class DataReferenceStatus(StrEnum):
    """Declared data/reference registry lifecycle."""

    AVAILABLE = "available"
    PROVISIONAL = "provisional"
    DEPRECATED = "deprecated"
    BLOCKED = "blocked"


class DriftMetric(StrEnum):
    """Thresholded monitor metric families."""

    MEAN_DELTA = "mean_delta"
    PSI = "psi"
    KS_PROXY = "ks_proxy"
    MISSINGNESS_DELTA = "missingness_delta"


@dataclass(frozen=True, slots=True)
class PlatformAlphaIssue:
    """Retained runtime, registry, or monitor issue."""

    code: str
    message: str
    raw_hash: str
    severity: str = "warning"
    row_number: int | None = None
    context_key: str | None = None
    raw_record: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty(self.code, "platform alpha issue code")
        require_non_empty(self.message, "platform alpha issue message")
        require_non_empty(self.raw_hash, "platform alpha issue raw_hash")
        if self.row_number is not None and self.row_number < 1:
            raise ValidationError("platform alpha issue row_number must be positive")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ExecutionEvent:
    """One typed, content-addressed event in an execution history."""

    event_id: str
    execution_id: str
    sequence: int
    kind: ExecutionEventKind
    context_key: str
    occurred_at: str
    input_hash: str | None
    output_hash: str | None
    source_ids: tuple[str, ...]
    message: str
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "event_id",
            "execution_id",
            "context_key",
            "occurred_at",
            "message",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if self.sequence < 1:
            raise ValidationError("execution event sequence must be positive")
        if not self.source_ids:
            raise ValidationError("execution event requires source IDs")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ExecutionLedger:
    """Immutable append-only execution ledger snapshot."""

    execution_id: str
    context_key: str
    state: RuntimeAlphaState
    events: tuple[ExecutionEvent, ...]
    last_sequence: int
    issues: tuple[PlatformAlphaIssue, ...]
    warnings: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.execution_id, "execution_id")
        require_non_empty(self.context_key, "context_key")
        if self.last_sequence != len(self.events):
            raise ValidationError("execution ledger last_sequence must equal event count")
        sequences = tuple(event.sequence for event in self.events)
        if sequences != tuple(range(1, len(self.events) + 1)):
            raise ValidationError("execution ledger sequences must be contiguous")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class EventSourcedExecutionLedger:
    """Build, append, and replay controlled execution event histories."""

    _TRANSITIONS = {
        None: {ExecutionEventKind.REQUESTED},
        ExecutionEventKind.REQUESTED: {
            ExecutionEventKind.PLANNED,
            ExecutionEventKind.ADMITTED,
            ExecutionEventKind.REJECTED,
            ExecutionEventKind.CANCELLED,
        },
        ExecutionEventKind.PLANNED: {
            ExecutionEventKind.ADMITTED,
            ExecutionEventKind.REJECTED,
            ExecutionEventKind.CANCELLED,
        },
        ExecutionEventKind.ADMITTED: {
            ExecutionEventKind.STARTED,
            ExecutionEventKind.REJECTED,
            ExecutionEventKind.CANCELLED,
        },
        ExecutionEventKind.STARTED: {
            ExecutionEventKind.CHECKPOINT,
            ExecutionEventKind.COMPLETED,
            ExecutionEventKind.FAILED,
            ExecutionEventKind.CANCELLED,
        },
        ExecutionEventKind.CHECKPOINT: {
            ExecutionEventKind.CHECKPOINT,
            ExecutionEventKind.COMPLETED,
            ExecutionEventKind.FAILED,
            ExecutionEventKind.CANCELLED,
        },
        ExecutionEventKind.FAILED: set(),
        ExecutionEventKind.REJECTED: set(),
        ExecutionEventKind.CANCELLED: set(),
        ExecutionEventKind.COMPLETED: set(),
    }

    def start(self, execution_id: str, *, context_key: str) -> ExecutionLedger:
        return ExecutionLedger(
            execution_id=execution_id,
            context_key=context_key,
            state=RuntimeAlphaState.ABSTAINED,
            events=(),
            last_sequence=0,
            issues=(),
            warnings=(
                "An empty ledger has no execution claim; a requested event is required "
                "before replay.",
                "Ledger events describe controlled runtime history and do not validate "
                "scientific content.",
            ),
            content_address=content_hash(
                {"execution_id": execution_id, "context_key": context_key, "events": ()}
            ),
        )

    def append(
        self,
        ledger: ExecutionLedger,
        event: ExecutionEvent | Mapping[str, Any],
    ) -> ExecutionLedger:
        try:
            item = _coerce_event(
                event,
                execution_id=ledger.execution_id,
                context_key=ledger.context_key,
                sequence=ledger.last_sequence + 1,
            )
        except (TypeError, ValueError, ValidationError) as exc:
            issue = PlatformAlphaIssue(
                "invalid_execution_event", str(exc), content_hash(event), severity="error"
            )
            return self._snapshot(ledger, ledger.events, ledger.state, ledger.issues + (issue,))
        issues = list(ledger.issues)
        if item.execution_id != ledger.execution_id:
            issues.append(
                PlatformAlphaIssue(
                    "execution_id_mismatch",
                    "event belongs to another execution",
                    item.event_id,
                    severity="error",
                )
            )
            return self._snapshot(ledger, ledger.events, RuntimeAlphaState.PARTIAL, tuple(issues))
        if item.context_key != ledger.context_key:
            issues.append(
                PlatformAlphaIssue(
                    "context_mismatch",
                    "event is outside the ledger context",
                    item.event_id,
                    severity="warning",
                    context_key=item.context_key,
                )
            )
            return self._snapshot(
                ledger, ledger.events, RuntimeAlphaState.OUT_OF_DOMAIN, tuple(issues)
            )
        if any(existing.event_id == item.event_id for existing in ledger.events):
            issues.append(
                PlatformAlphaIssue(
                    "duplicate_event_id",
                    "event ID already exists in ledger",
                    item.event_id,
                    severity="error",
                )
            )
            return self._snapshot(ledger, ledger.events, RuntimeAlphaState.PARTIAL, tuple(issues))
        previous_kind = ledger.events[-1].kind if ledger.events else None
        if item.kind not in self._TRANSITIONS[previous_kind]:
            issues.append(
                PlatformAlphaIssue(
                    "invalid_event_transition",
                    f"{item.kind.value} cannot follow "
                    f"{previous_kind.value if previous_kind else 'empty ledger'}",
                    item.event_id,
                    severity="error",
                )
            )
            return self._snapshot(ledger, ledger.events, RuntimeAlphaState.BLOCKED, tuple(issues))
        state = self._state_for_event(item.kind)
        return self._snapshot(ledger, ledger.events + (item,), state, tuple(issues))

    def replay(
        self,
        events: Iterable[ExecutionEvent | Mapping[str, Any]],
        *,
        execution_id: str,
        context_key: str,
    ) -> ExecutionLedger:
        ledger = self.start(execution_id, context_key=context_key)
        for value in events:
            ledger = self.append(ledger, value)
        return ledger

    def _snapshot(
        self,
        ledger: ExecutionLedger,
        events: tuple[ExecutionEvent, ...],
        state: RuntimeAlphaState,
        issues: tuple[PlatformAlphaIssue, ...],
    ) -> ExecutionLedger:
        return ExecutionLedger(
            execution_id=ledger.execution_id,
            context_key=ledger.context_key,
            state=state,
            events=events,
            last_sequence=len(events),
            issues=issues,
            warnings=ledger.warnings,
            content_address=content_hash(
                {
                    "execution_id": ledger.execution_id,
                    "context_key": ledger.context_key,
                    "state": state,
                    "events": events,
                    "issues": issues,
                }
            ),
        )

    @staticmethod
    def _state_for_event(kind: ExecutionEventKind) -> RuntimeAlphaState:
        return {
            ExecutionEventKind.REQUESTED: RuntimeAlphaState.READY_FOR_REVIEW,
            ExecutionEventKind.PLANNED: RuntimeAlphaState.READY_FOR_REVIEW,
            ExecutionEventKind.ADMITTED: RuntimeAlphaState.READY_FOR_REVIEW,
            ExecutionEventKind.STARTED: RuntimeAlphaState.READY_FOR_REVIEW,
            ExecutionEventKind.CHECKPOINT: RuntimeAlphaState.READY_FOR_REVIEW,
            ExecutionEventKind.COMPLETED: RuntimeAlphaState.COMPLETED,
            ExecutionEventKind.FAILED: RuntimeAlphaState.FAILED,
            ExecutionEventKind.REJECTED: RuntimeAlphaState.REJECTED,
            ExecutionEventKind.CANCELLED: RuntimeAlphaState.REJECTED,
        }[kind]


@dataclass(frozen=True, slots=True)
class ModelRegistryRecord:
    """Versioned model artifact and exact-context compatibility contract."""

    model_id: str
    version: str
    model_family: str
    artifact_digest: str
    input_contract: str
    output_contract: str
    supported_contexts: tuple[str, ...]
    status: ModelStatus
    source_ids: tuple[str, ...]
    license_id: str
    evaluation_receipt: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "model_id",
            "version",
            "model_family",
            "artifact_digest",
            "input_contract",
            "output_contract",
            "license_id",
            "evaluation_receipt",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if not self.supported_contexts or not self.source_ids:
            raise ValidationError("model registry record requires contexts and source IDs")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class ModelResolutionState(StrEnum):
    """Model compatibility result state."""

    COMPATIBLE = "compatible"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    OUT_OF_DOMAIN = "out_of_domain"
    ABSTAINED = "abstained"


@dataclass(frozen=True, slots=True)
class ModelResolution:
    """Resolved model record with explicit compatibility blockers."""

    model_id: str
    requested_version: str | None
    context_key: str
    state: ModelResolutionState
    selected_version: str | None
    artifact_digest: str | None
    input_contract: str | None
    output_contract: str | None
    blockers: tuple[str, ...]
    source_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ModelRegistrySnapshot:
    """Immutable model registry snapshot."""

    records: tuple[ModelRegistryRecord, ...]
    content_address: str

    def register(self, record: ModelRegistryRecord) -> ModelRegistrySnapshot:
        if any(
            item.model_id == record.model_id and item.version == record.version
            for item in self.records
        ):
            raise ValidationError("model registry model_id/version already exists")
        records = self.records + (record,)
        return ModelRegistrySnapshot(records=records, content_address=content_hash(records))

    def resolve(
        self,
        model_id: str,
        *,
        context_key: str,
        version: str | None = None,
        input_contract: str | None = None,
        output_contract: str | None = None,
    ) -> ModelResolution:
        candidates = tuple(item for item in self.records if item.model_id == model_id)
        if version is not None:
            candidates = tuple(item for item in candidates if item.version == version)
        if not candidates:
            return ModelResolution(
                model_id,
                version,
                context_key,
                ModelResolutionState.ABSTAINED,
                None,
                None,
                None,
                None,
                ("model_version_not_registered",),
                (),
                content_hash(
                    {"model_id": model_id, "version": version, "context_key": context_key}
                ),
            )
        candidates = tuple(sorted(candidates, key=lambda item: item.version, reverse=True))
        selected = candidates[0]
        blockers: list[str] = []
        if context_key not in selected.supported_contexts:
            blockers.append("context_not_supported")
        if input_contract is not None and selected.input_contract != input_contract:
            blockers.append("input_contract_mismatch")
        if output_contract is not None and selected.output_contract != output_contract:
            blockers.append("output_contract_mismatch")
        if selected.status == ModelStatus.BLOCKED:
            blockers.append("model_status_blocked")
        if selected.status == ModelStatus.DEPRECATED:
            blockers.append("model_status_deprecated")
        if "context_not_supported" in blockers:
            state = ModelResolutionState.OUT_OF_DOMAIN
        elif blockers:
            state = ModelResolutionState.BLOCKED
        elif selected.status == ModelStatus.CANDIDATE:
            state = ModelResolutionState.PARTIAL
        else:
            state = ModelResolutionState.COMPATIBLE
        return ModelResolution(
            model_id=model_id,
            requested_version=version,
            context_key=context_key,
            state=state,
            selected_version=selected.version,
            artifact_digest=selected.artifact_digest,
            input_contract=selected.input_contract,
            output_contract=selected.output_contract,
            blockers=tuple(blockers),
            source_ids=selected.source_ids,
            content_address=content_hash(
                {
                    "record": selected,
                    "context_key": context_key,
                    "state": state,
                    "blockers": blockers,
                }
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class ModelRegistry:
    """Convenience builder for immutable model registry snapshots."""

    def __init__(self, records: Iterable[ModelRegistryRecord] = ()) -> None:
        self._snapshot = ModelRegistrySnapshot(
            records=tuple(records), content_address=content_hash(tuple(records))
        )

    @classmethod
    def from_mappings(
        cls, records: Iterable[ModelRegistryRecord | Mapping[str, Any]]
    ) -> ModelRegistry:
        return cls(_coerce_model(value) for value in records)

    @property
    def snapshot(self) -> ModelRegistrySnapshot:
        return self._snapshot

    def register(self, record: ModelRegistryRecord) -> ModelRegistrySnapshot:
        self._snapshot = self._snapshot.register(record)
        return self._snapshot


@dataclass(frozen=True, slots=True)
class DataReferenceRecord:
    """Versioned data/reference artifact and reproducibility receipt."""

    dataset_id: str
    version: str
    reference_kind: str
    source_uri: str
    checksum: str
    format: str
    schema_hash: str
    supported_contexts: tuple[str, ...]
    coordinate_system: str
    license_id: str
    status: DataReferenceStatus
    source_ids: tuple[str, ...]
    retrieval_receipt: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "dataset_id",
            "version",
            "reference_kind",
            "source_uri",
            "checksum",
            "format",
            "schema_hash",
            "coordinate_system",
            "license_id",
            "retrieval_receipt",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if not self.supported_contexts or not self.source_ids:
            raise ValidationError("data reference requires contexts and source IDs")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DataReferenceResolution:
    """Resolved data/reference compatibility result."""

    dataset_id: str
    requested_version: str | None
    context_key: str
    state: RuntimeAlphaState
    selected_version: str | None
    checksum: str | None
    coordinate_system: str | None
    license_id: str | None
    blockers: tuple[str, ...]
    source_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DataReferenceRegistrySnapshot:
    """Immutable data/reference registry snapshot."""

    records: tuple[DataReferenceRecord, ...]
    content_address: str

    def register(self, record: DataReferenceRecord) -> DataReferenceRegistrySnapshot:
        if any(
            item.dataset_id == record.dataset_id and item.version == record.version
            for item in self.records
        ):
            raise ValidationError("data registry dataset_id/version already exists")
        records = self.records + (record,)
        return DataReferenceRegistrySnapshot(records=records, content_address=content_hash(records))

    def resolve(
        self,
        dataset_id: str,
        *,
        context_key: str,
        version: str | None = None,
        coordinate_system: str | None = None,
        license_id: str | None = None,
    ) -> DataReferenceResolution:
        candidates = tuple(item for item in self.records if item.dataset_id == dataset_id)
        if version is not None:
            candidates = tuple(item for item in candidates if item.version == version)
        if not candidates:
            return DataReferenceResolution(
                dataset_id,
                version,
                context_key,
                RuntimeAlphaState.ABSTAINED,
                None,
                None,
                None,
                None,
                ("dataset_version_not_registered",),
                (),
                content_hash(
                    {"dataset_id": dataset_id, "version": version, "context_key": context_key}
                ),
            )
        selected = sorted(candidates, key=lambda item: item.version, reverse=True)[0]
        blockers: list[str] = []
        if context_key not in selected.supported_contexts:
            blockers.append("context_not_supported")
        if coordinate_system is not None and selected.coordinate_system != coordinate_system:
            blockers.append("coordinate_system_mismatch")
        if license_id is not None and selected.license_id != license_id:
            blockers.append("license_mismatch")
        if selected.status == DataReferenceStatus.BLOCKED:
            blockers.append("reference_status_blocked")
        if selected.status == DataReferenceStatus.DEPRECATED:
            blockers.append("reference_status_deprecated")
        state = (
            RuntimeAlphaState.OUT_OF_DOMAIN
            if "context_not_supported" in blockers
            else RuntimeAlphaState.BLOCKED
            if blockers
            else RuntimeAlphaState.REVIEW_REQUIRED
            if selected.status == DataReferenceStatus.PROVISIONAL
            else RuntimeAlphaState.COMPATIBLE
        )
        return DataReferenceResolution(
            dataset_id=dataset_id,
            requested_version=version,
            context_key=context_key,
            state=state,
            selected_version=selected.version,
            checksum=selected.checksum,
            coordinate_system=selected.coordinate_system,
            license_id=selected.license_id,
            blockers=tuple(blockers),
            source_ids=selected.source_ids,
            content_address=content_hash(
                {
                    "record": selected,
                    "context_key": context_key,
                    "state": state,
                    "blockers": blockers,
                }
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class DataReferenceRegistry:
    """Convenience builder for immutable data/reference snapshots."""

    def __init__(self, records: Iterable[DataReferenceRecord] = ()) -> None:
        values = tuple(records)
        self._snapshot = DataReferenceRegistrySnapshot(
            records=values, content_address=content_hash(values)
        )

    @classmethod
    def from_mappings(
        cls, records: Iterable[DataReferenceRecord | Mapping[str, Any]]
    ) -> DataReferenceRegistry:
        return cls(_coerce_data(value) for value in records)

    @property
    def snapshot(self) -> DataReferenceRegistrySnapshot:
        return self._snapshot

    def register(self, record: DataReferenceRecord) -> DataReferenceRegistrySnapshot:
        self._snapshot = self._snapshot.register(record)
        return self._snapshot


@dataclass(frozen=True, slots=True)
class DriftObservation:
    """Reference/current feature summary for thresholded monitoring."""

    observation_id: str
    monitor_id: str
    feature_id: str
    context_key: str
    metric: DriftMetric
    reference_value: float
    current_value: float
    watch_threshold: float
    drift_threshold: float
    in_domain: bool
    support_score: float | None
    source_ids: tuple[str, ...]
    raw_hash: str
    reference_bins: tuple[float, ...] = ()
    current_bins: tuple[float, ...] = ()
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "observation_id",
            "monitor_id",
            "feature_id",
            "context_key",
            "raw_hash",
        ):
            require_non_empty(str(getattr(self, name)), name)
        for name in ("reference_value", "current_value", "watch_threshold", "drift_threshold"):
            if not isfinite(float(getattr(self, name))) or float(getattr(self, name)) < 0:
                raise ValidationError(f"drift {name} must be finite and non-negative")
        if self.watch_threshold > self.drift_threshold:
            raise ValidationError("drift watch_threshold cannot exceed drift_threshold")
        if self.support_score is not None and not 0 <= self.support_score <= 1:
            raise ValidationError("drift support_score must be between zero and one")
        if not self.source_ids:
            raise ValidationError("drift observation requires source IDs")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DriftFinding:
    """One metric result retaining drift and OOD dimensions separately."""

    observation_id: str
    feature_id: str
    metric: DriftMetric
    metric_value: float
    state: RuntimeAlphaState
    in_domain: bool
    support_score: float | None
    reasons: tuple[str, ...]
    source_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DriftMonitorReport:
    """Aggregate drift/OOD review report."""

    monitor_id: str
    context_key: str
    state: RuntimeAlphaState
    findings: tuple[DriftFinding, ...]
    drifted_feature_ids: tuple[str, ...]
    watch_feature_ids: tuple[str, ...]
    out_of_domain_feature_ids: tuple[str, ...]
    issues: tuple[PlatformAlphaIssue, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class DriftAndOODMonitor:
    """Evaluate declared threshold signals without inferring model validity."""

    def evaluate(
        self,
        observations: Iterable[DriftObservation | Mapping[str, Any]],
        *,
        monitor_id: str,
        context_key: str,
    ) -> DriftMonitorReport:
        require_non_empty(monitor_id, "monitor_id")
        require_non_empty(context_key, "context_key")
        findings: list[DriftFinding] = []
        issues: list[PlatformAlphaIssue] = []
        for row_number, value in enumerate(tuple(observations), start=1):
            try:
                item = _coerce_drift(value)
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    PlatformAlphaIssue(
                        "invalid_drift_observation",
                        str(exc),
                        content_hash(value),
                        severity="error",
                        row_number=row_number,
                    )
                )
                continue
            if item.monitor_id != monitor_id:
                issues.append(
                    PlatformAlphaIssue(
                        "monitor_id_mismatch",
                        "observation belongs to another monitor",
                        item.raw_hash,
                        row_number=row_number,
                    )
                )
                continue
            if item.context_key != context_key:
                issues.append(
                    PlatformAlphaIssue(
                        "context_mismatch",
                        "drift observation is outside requested context",
                        item.raw_hash,
                        row_number=row_number,
                        context_key=item.context_key,
                    )
                )
                continue
            metric_value = self._metric_value(item)
            reasons: list[str] = []
            if not item.in_domain:
                reasons.append("declared_out_of_domain")
            if item.support_score is not None and item.support_score < 0.5:
                reasons.append("support_score_below_review_floor")
            if metric_value >= item.drift_threshold:
                reasons.append("metric_exceeds_drift_threshold")
                state = RuntimeAlphaState.DRIFT
            elif metric_value >= item.watch_threshold:
                reasons.append("metric_exceeds_watch_threshold")
                state = RuntimeAlphaState.WATCH
            else:
                state = RuntimeAlphaState.READY_FOR_REVIEW
            if not item.in_domain or (item.support_score is not None and item.support_score < 0.5):
                state = RuntimeAlphaState.OUT_OF_DOMAIN
            findings.append(
                DriftFinding(
                    observation_id=item.observation_id,
                    feature_id=item.feature_id,
                    metric=item.metric,
                    metric_value=round(metric_value, 9),
                    state=state,
                    in_domain=item.in_domain,
                    support_score=item.support_score,
                    reasons=tuple(reasons),
                    source_ids=item.source_ids,
                    content_address=content_hash(
                        {"observation": item, "metric_value": metric_value, "state": state}
                    ),
                )
            )
        drifted = tuple(
            sorted({item.feature_id for item in findings if item.state == RuntimeAlphaState.DRIFT})
        )
        watched = tuple(
            sorted({item.feature_id for item in findings if item.state == RuntimeAlphaState.WATCH})
        )
        out_of_domain = tuple(
            sorted(
                {
                    item.feature_id
                    for item in findings
                    if item.state == RuntimeAlphaState.OUT_OF_DOMAIN
                }
            )
        )
        if not findings:
            state = (
                RuntimeAlphaState.OUT_OF_DOMAIN
                if any(issue.code == "context_mismatch" for issue in issues)
                else RuntimeAlphaState.ABSTAINED
            )
        elif out_of_domain:
            state = RuntimeAlphaState.OUT_OF_DOMAIN
        elif drifted:
            state = RuntimeAlphaState.DRIFT
        elif watched:
            state = RuntimeAlphaState.WATCH
        elif any(issue.severity == "error" for issue in issues):
            state = RuntimeAlphaState.PARTIAL
        else:
            state = RuntimeAlphaState.READY_FOR_REVIEW
        return DriftMonitorReport(
            monitor_id=monitor_id,
            context_key=context_key,
            state=state,
            findings=tuple(findings),
            drifted_feature_ids=drifted,
            watch_feature_ids=watched,
            out_of_domain_feature_ids=out_of_domain,
            issues=tuple(issues),
            warnings=(
                "Drift thresholds are monitoring signals, not proof of model failure or data "
                "invalidity.",
                "Out-of-domain state indicates a declared support boundary or low support "
                "score and requires review.",
            ),
            content_address=content_hash(
                {
                    "monitor_id": monitor_id,
                    "context_key": context_key,
                    "state": state,
                    "findings": findings,
                    "issues": issues,
                }
            ),
        )

    @staticmethod
    def _metric_value(item: DriftObservation) -> float:
        if item.metric == DriftMetric.MEAN_DELTA:
            return abs(item.current_value - item.reference_value)
        if item.metric == DriftMetric.MISSINGNESS_DELTA:
            return abs(item.current_value - item.reference_value)
        if item.metric == DriftMetric.KS_PROXY:
            return abs(item.current_value - item.reference_value)
        if item.reference_bins and item.current_bins:
            if len(item.reference_bins) != len(item.current_bins):
                return float("inf")
            reference_total = sum(item.reference_bins) or 1.0
            current_total = sum(item.current_bins) or 1.0
            value = 0.0
            for reference, current in zip(item.reference_bins, item.current_bins, strict=True):
                p = max(reference / reference_total, 1e-12)
                q = max(current / current_total, 1e-12)
                value += (p - q) * log(p / q)
            return value
        return abs(item.current_value - item.reference_value)


def _coerce_event(
    value: ExecutionEvent | Mapping[str, Any],
    *,
    execution_id: str,
    context_key: str,
    sequence: int,
) -> ExecutionEvent:
    if isinstance(value, ExecutionEvent):
        return value
    if not isinstance(value, Mapping):
        raise ValidationError("execution event must be a mapping")
    return ExecutionEvent(
        event_id=str(value.get("event_id", value.get("id", f"event-{sequence}"))),
        execution_id=str(value.get("execution_id", execution_id)),
        sequence=int(value.get("sequence", sequence)),
        kind=ExecutionEventKind(str(value.get("kind", ExecutionEventKind.REQUESTED.value))),
        context_key=str(value.get("context_key", context_key)),
        occurred_at=str(value.get("occurred_at", "unspecified")),
        input_hash=(None if value.get("input_hash") in (None, "") else str(value["input_hash"])),
        output_hash=(None if value.get("output_hash") in (None, "") else str(value["output_hash"])),
        source_ids=_strings(value.get("source_ids", value.get("source_id", ("runtime-input",)))),
        message=str(value.get("message", "declared execution event")),
        attributes=dict(value.get("attributes", {})),
    )


def _coerce_model(value: ModelRegistryRecord | Mapping[str, Any]) -> ModelRegistryRecord:
    if isinstance(value, ModelRegistryRecord):
        return value
    if not isinstance(value, Mapping):
        raise ValidationError("model registry record must be a mapping")
    return ModelRegistryRecord(
        model_id=str(value.get("model_id", value.get("id", ""))),
        version=str(value.get("version", "")),
        model_family=str(value.get("model_family", value.get("family", "unspecified"))),
        artifact_digest=str(value.get("artifact_digest", value.get("artifact_hash", ""))),
        input_contract=str(value.get("input_contract", "unspecified")),
        output_contract=str(value.get("output_contract", "unspecified")),
        supported_contexts=_strings(value.get("supported_contexts", value.get("contexts", ()))),
        status=ModelStatus(str(value.get("status", ModelStatus.CANDIDATE.value))),
        source_ids=_strings(value.get("source_ids", value.get("source_id", ("model-registry",)))),
        license_id=str(value.get("license_id", value.get("license", "unspecified"))),
        evaluation_receipt=str(value.get("evaluation_receipt", value.get("evaluation_hash", ""))),
        metadata=dict(value.get("metadata", {})),
    )


def _coerce_data(value: DataReferenceRecord | Mapping[str, Any]) -> DataReferenceRecord:
    if isinstance(value, DataReferenceRecord):
        return value
    if not isinstance(value, Mapping):
        raise ValidationError("data reference record must be a mapping")
    return DataReferenceRecord(
        dataset_id=str(value.get("dataset_id", value.get("id", ""))),
        version=str(value.get("version", "")),
        reference_kind=str(value.get("reference_kind", value.get("kind", "dataset"))),
        source_uri=str(value.get("source_uri", value.get("uri", ""))),
        checksum=str(value.get("checksum", "")),
        format=str(value.get("format", "json")),
        schema_hash=str(value.get("schema_hash", "")),
        supported_contexts=_strings(value.get("supported_contexts", value.get("contexts", ()))),
        coordinate_system=str(value.get("coordinate_system", "unspecified")),
        license_id=str(value.get("license_id", value.get("license", "unspecified"))),
        status=DataReferenceStatus(str(value.get("status", DataReferenceStatus.PROVISIONAL.value))),
        source_ids=_strings(value.get("source_ids", value.get("source_id", ("data-registry",)))),
        retrieval_receipt=str(value.get("retrieval_receipt", value.get("retrieval_hash", ""))),
        metadata=dict(value.get("metadata", {})),
    )


def _coerce_drift(value: DriftObservation | Mapping[str, Any]) -> DriftObservation:
    if isinstance(value, DriftObservation):
        return value
    if not isinstance(value, Mapping):
        raise ValidationError("drift observation must be a mapping")
    return DriftObservation(
        observation_id=str(value.get("observation_id", value.get("id", ""))),
        monitor_id=str(value.get("monitor_id", "monitor")),
        feature_id=str(value.get("feature_id", value.get("feature", ""))),
        context_key=str(value.get("context_key", value.get("context", ""))),
        metric=DriftMetric(str(value.get("metric", DriftMetric.MEAN_DELTA.value))),
        reference_value=float(value.get("reference_value", value.get("reference", 0.0))),
        current_value=float(value.get("current_value", value.get("current", 0.0))),
        watch_threshold=float(value.get("watch_threshold", 0.1)),
        drift_threshold=float(value.get("drift_threshold", 0.2)),
        in_domain=_as_bool(value.get("in_domain", True)),
        support_score=(
            None if value.get("support_score") is None else float(value["support_score"])
        ),
        source_ids=_strings(value.get("source_ids", value.get("source_id", ("monitor-input",)))),
        raw_hash=str(value.get("raw_hash", content_hash(dict(value)))),
        reference_bins=tuple(float(item) for item in value.get("reference_bins", ())),
        current_bins=tuple(float(item) for item in value.get("current_bins", ())),
        attributes=dict(value.get("attributes", {})),
    )


def _strings(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,) if value.strip() else ()
    if value is None:
        return ()
    return tuple(dict.fromkeys(str(item) for item in value if str(item).strip()))


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


__all__ = [
    "DataReferenceRecord",
    "DataReferenceRegistry",
    "DataReferenceRegistrySnapshot",
    "DataReferenceResolution",
    "DataReferenceStatus",
    "DriftAndOODMonitor",
    "DriftFinding",
    "DriftMetric",
    "DriftMonitorReport",
    "DriftObservation",
    "EventSourcedExecutionLedger",
    "ExecutionEvent",
    "ExecutionEventKind",
    "ExecutionLedger",
    "ModelRegistry",
    "ModelRegistryRecord",
    "ModelRegistrySnapshot",
    "ModelResolution",
    "ModelResolutionState",
    "ModelStatus",
    "PlatformAlphaIssue",
    "RuntimeAlphaState",
]
