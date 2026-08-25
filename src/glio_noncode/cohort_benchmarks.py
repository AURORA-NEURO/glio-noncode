"""Deterministic cohort split, leakage, calibration, risk, and transport benchmarks.

This module is the shared benchmark boundary for aggregate cohort records. It
does not estimate clinical performance, validate a model, or turn a public
fixture into a patient cohort. It does provide the mechanics needed to keep a
benchmark honest: deterministic group or time splits, cross-split lineage
checks, held-out calibration metrics, selective risk-coverage curves, and
declared source-to-target transport comparisons.

All reports are bounded, content-addressed, and explicit about review or
abstention. Direct subject, sample, contact, credential, model, agent, and
language fields are rejected before records enter the benchmark.
"""

from __future__ import annotations

import csv
import io
import json
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from math import log
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty


COHORT_BENCHMARK_VERSION = "cohort-benchmark-v1"
COHORT_BENCHMARK_SCHEMA_VERSION = "cohort-benchmark-schema-v1"
COHORT_BENCHMARK_RECORD_SCHEMA_VERSION = "cohort-benchmark-record-v1"
COHORT_BENCHMARK_MAX_RECORDS = 1_000_000
COHORT_BENCHMARK_MAX_BINS = 100
COHORT_BENCHMARK_MAX_POINTS = 101
COHORT_BENCHMARK_MAX_DOMAINS = 1_000

_FORBIDDEN_KEYS = frozenset(
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
        "contact",
        "contact_name",
        "credential",
        "credential_value",
        "email",
        "generated_by",
        "individual",
        "individual_id",
        "language",
        "medical_record_number",
        "model",
        "model_id",
        "model_name",
        "model_version",
        "participant",
        "participant_id",
        "patient",
        "patient_id",
        "phone",
        "programming_language",
        "sample",
        "sample_id",
        "secret",
        "secret_key",
        "subject",
        "subject_id",
        "token",
    }
)


class BenchmarkState(StrEnum):
    """Release state for one benchmark plane or suite."""

    ACCEPTED = "accepted"
    REVIEW = "review"
    BLOCKED = "blocked"
    ABSTAINED = "abstained"


class SplitStrategy(StrEnum):
    """Deterministic cohort partition policies."""

    GROUP = "group"
    SOURCE = "source"
    CONTEXT = "context"
    HASH = "hash"
    TEMPORAL = "temporal"


class LeakageSeverity(StrEnum):
    """Severity of a split integrity finding."""

    WARNING = "warning"
    ERROR = "error"


def _text(value: Any, field: str) -> str:
    return require_non_empty(str(value), field)


def _bounded(value: Any, field: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{field} must be numeric") from exc
    if not 0.0 <= result <= 1.0:
        raise ValidationError(f"{field} must be between 0 and 1")
    return round(result, 8)


def _non_negative(value: Any, field: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{field} must be numeric") from exc
    if result < 0.0:
        raise ValidationError(f"{field} must not be negative")
    return round(result, 8)


def _unique_texts(values: Iterable[Any]) -> tuple[str, ...]:
    return tuple(sorted({str(value).strip() for value in values if str(value).strip()}))


def _as_text_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    values = (value,) if isinstance(value, str) else tuple(value)
    if isinstance(value, str):
        values = tuple(part.strip() for part in value.replace(",", "|").split("|"))
    return _unique_texts(values)


def _forbidden_paths(value: Any, path: str = "$") -> tuple[str, ...]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            text = str(key)
            child = f"{path}.{text}"
            if text.casefold() in _FORBIDDEN_KEYS:
                found.append(child)
            found.extend(_forbidden_paths(item, child))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            found.extend(_forbidden_paths(item, f"{path}[{index}]"))
    return tuple(sorted(set(found)))


def _context_key(value: Any) -> str:
    context = _text(value, "context_key")
    parts = tuple(part.strip() for part in context.split("|"))
    if len(parts) != 6 or any(not part for part in parts):
        raise ValidationError(
            "context_key must contain six non-empty dimensions: "
            "genome_build|disease_class|age_group|cell_state|territory|treatment_phase"
        )
    return "|".join(parts)


def _label(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return int(value)
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError("label must be binary") from exc
    if numeric not in {0.0, 1.0}:
        raise ValidationError("label must be 0 or 1")
    return int(numeric)


def _score(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return _bounded(value, "score")


def _parse_datetime(value: str | None, field: str = "collected_at") -> datetime | None:
    if value is None or not str(value).strip():
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValidationError(f"{field} must be ISO-8601") from exc


@dataclass(frozen=True, slots=True)
class CohortBenchmarkRecord:
    """One aggregate benchmark row with no direct subject-level identity."""

    record_id: str
    cohort_id: str
    domain_id: str
    source_id: str
    context_key: str
    label: int | None
    score: float | None
    uncertainty: float
    group_id: str
    lineage_key: str | None
    feature_keys: tuple[str, ...]
    collected_at: str | None
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in (
            "record_id",
            "cohort_id",
            "domain_id",
            "source_id",
            "context_key",
            "group_id",
        ):
            _text(getattr(self, name), name)
        object.__setattr__(self, "context_key", _context_key(self.context_key))
        if self.label not in {None, 0, 1}:
            raise ValidationError("cohort benchmark label must be 0, 1, or absent")
        if self.score is not None:
            object.__setattr__(self, "score", _bounded(self.score, "score"))
        object.__setattr__(self, "uncertainty", _non_negative(self.uncertainty, "uncertainty"))
        object.__setattr__(self, "feature_keys", _unique_texts(self.feature_keys))
        object.__setattr__(self, "tags", _unique_texts(self.tags))
        if self.collected_at is not None:
            _parse_datetime(self.collected_at)
        if self.lineage_key is not None and not str(self.lineage_key).strip():
            object.__setattr__(self, "lineage_key", None)

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "CohortBenchmarkRecord":
        if not isinstance(raw, Mapping):
            raise ValidationError("cohort benchmark record must be an object")
        forbidden = _forbidden_paths(raw)
        if forbidden:
            raise ValidationError(
                "cohort benchmark record contains forbidden public-boundary keys: "
                + ", ".join(forbidden)
            )
        metadata = raw.get("metadata", {})
        if metadata is not None and not isinstance(metadata, Mapping):
            raise ValidationError("benchmark metadata must be an object when supplied")
        return cls(
            record_id=str(raw.get("record_id", raw.get("id", ""))),
            cohort_id=str(raw.get("cohort_id", raw.get("cohort", "default-cohort"))),
            domain_id=str(raw.get("domain_id", raw.get("domain", raw.get("cohort_id", "default-domain")))),
            source_id=str(raw.get("source_id", raw.get("source", "unknown-source"))),
            context_key=str(raw.get("context_key", raw.get("context", ""))),
            label=_label(raw.get("label", raw.get("target", raw.get("positive")))),
            score=_score(
                raw.get(
                    "score",
                    raw.get("predicted_score", raw.get("probability", raw.get("prediction"))),
                )
            ),
            uncertainty=_non_negative(raw.get("uncertainty", 0.0), "uncertainty"),
            group_id=str(
                raw.get(
                    "group_id",
                    raw.get("group", raw.get("cohort_group", raw.get("cohort_id", "default-group"))),
                )
            ),
            lineage_key=(
                None
                if raw.get("lineage_key", raw.get("provenance_key")) is None
                else str(raw.get("lineage_key", raw.get("provenance_key")))
            ),
            feature_keys=_as_text_tuple(raw.get("feature_keys", raw.get("features", raw.get("feature_key")))),
            collected_at=(
                None
                if raw.get("collected_at", raw.get("timestamp", raw.get("date"))) is None
                else str(raw.get("collected_at", raw.get("timestamp", raw.get("date"))))
            ),
            tags=_as_text_tuple(raw.get("tags", ())),
        )

    @property
    def content_address(self) -> str:
        return content_hash(self._content_body(), prefix="cohort-benchmark-record")

    def _content_body(self) -> dict[str, Any]:
        return {
            "schema_version": COHORT_BENCHMARK_RECORD_SCHEMA_VERSION,
            "record_id": self.record_id,
            "cohort_id": self.cohort_id,
            "domain_id": self.domain_id,
            "source_id": self.source_id,
            "context_key": self.context_key,
            "label": self.label,
            "score": self.score,
            "uncertainty": self.uncertainty,
            "group_id": self.group_id,
            "lineage_key": self.lineage_key,
            "feature_keys": self.feature_keys,
            "collected_at": self.collected_at,
            "tags": self.tags,
        }

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self._content_body() | {"content_address": self.content_address})


@dataclass(frozen=True, slots=True)
class SplitConfig:
    """Validated partition configuration."""

    strategy: SplitStrategy = SplitStrategy.GROUP
    train_fraction: float = 0.6
    validation_fraction: float = 0.2
    test_fraction: float = 0.2
    seed: str = "cohort-benchmark-seed"
    minimum_records_per_split: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "strategy", SplitStrategy(str(self.strategy)))
        for name in ("train_fraction", "validation_fraction", "test_fraction"):
            object.__setattr__(self, name, _bounded(getattr(self, name), name))
        if abs(
            self.train_fraction + self.validation_fraction + self.test_fraction - 1.0
        ) > 0.000001:
            raise ValidationError("split fractions must sum to 1")
        if not str(self.seed).strip():
            raise ValidationError("split seed must not be empty")
        if self.minimum_records_per_split < 0:
            raise ValidationError("minimum_records_per_split must not be negative")

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any] | None) -> "SplitConfig":
        value = raw or {}
        return cls(
            strategy=SplitStrategy(str(value.get("strategy", SplitStrategy.GROUP.value))),
            train_fraction=float(value.get("train_fraction", 0.6)),
            validation_fraction=float(value.get("validation_fraction", 0.2)),
            test_fraction=float(value.get("test_fraction", 0.2)),
            seed=str(value.get("seed", "cohort-benchmark-seed")),
            minimum_records_per_split=int(value.get("minimum_records_per_split", 1)),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortSplit:
    """Addressed record partition with group assignment evidence."""

    strategy: SplitStrategy
    seed: str
    train_ids: tuple[str, ...]
    validation_ids: tuple[str, ...]
    test_ids: tuple[str, ...]
    group_assignments: Mapping[str, str]
    counts: Mapping[str, int]
    issues: tuple[str, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return not self.issues

    def ids_for(self, split: str) -> tuple[str, ...]:
        normalized = str(split).casefold()
        if normalized == "train":
            return self.train_ids
        if normalized in {"validation", "valid", "val"}:
            return self.validation_ids
        if normalized == "test":
            return self.test_ids
        raise ValidationError(f"unknown split: {split}")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted": self.accepted}


def _split_name(fraction: float, value: float) -> str:
    if value < fraction:
        return "train"
    if value < fraction + (1.0 - fraction) / 2.0:
        return "validation"
    return "test"


def build_cohort_split(
    records: Sequence[CohortBenchmarkRecord],
    config: SplitConfig | None = None,
) -> CohortSplit:
    """Assign records without scattering one group across train and test."""

    selected = tuple(records)
    if not selected:
        raise ValidationError("cohort benchmark split requires records")
    selected_config = config or SplitConfig()
    if len(selected) > COHORT_BENCHMARK_MAX_RECORDS:
        raise ValidationError("cohort benchmark record ceiling was exceeded")
    ids = tuple(record.record_id for record in selected)
    duplicate_ids = tuple(sorted(record_id for record_id, count in Counter(ids).items() if count > 1))
    if selected_config.strategy is SplitStrategy.TEMPORAL:
        if any(record.collected_at is None for record in selected):
            raise ValidationError("temporal split requires collected_at for every record")
        ordered = sorted(
            selected,
            key=lambda record: (str(record.collected_at), record.record_id),
        )
        total = len(ordered)
        train_end = max(1, round(total * selected_config.train_fraction))
        validation_end = max(train_end, round(total * (selected_config.train_fraction + selected_config.validation_fraction)))
        assignment = {
            record.record_id: (
                "train"
                if index < train_end
                else "validation"
                if index < validation_end
                else "test"
            )
            for index, record in enumerate(ordered)
        }
        group_assignments = {
            record.record_id: assignment[record.record_id] for record in selected
        }
    else:
        groups: dict[str, list[CohortBenchmarkRecord]] = {}
        for record in selected:
            if selected_config.strategy is SplitStrategy.GROUP:
                key = record.group_id
            elif selected_config.strategy is SplitStrategy.SOURCE:
                key = record.source_id
            elif selected_config.strategy is SplitStrategy.CONTEXT:
                key = record.context_key
            else:
                key = record.record_id
            groups.setdefault(key, []).append(record)
        group_assignments: dict[str, str] = {}
        for key in sorted(groups):
            digest = content_hash({"seed": selected_config.seed, "group": key}, prefix="split")
            fraction = int(digest.split(":", 1)[1][:16], 16) / float(16**16)
            if fraction < selected_config.train_fraction:
                split = "train"
            elif fraction < selected_config.train_fraction + selected_config.validation_fraction:
                split = "validation"
            else:
                split = "test"
            group_assignments[key] = split
        assignment = {}
        for record in selected:
            if selected_config.strategy is SplitStrategy.GROUP:
                key = record.group_id
            elif selected_config.strategy is SplitStrategy.SOURCE:
                key = record.source_id
            elif selected_config.strategy is SplitStrategy.CONTEXT:
                key = record.context_key
            else:
                key = record.record_id
            assignment[record.record_id] = group_assignments[key]
    train = tuple(sorted(record_id for record_id in ids if assignment[record_id] == "train"))
    validation = tuple(
        sorted(record_id for record_id in ids if assignment[record_id] == "validation")
    )
    test = tuple(sorted(record_id for record_id in ids if assignment[record_id] == "test"))
    counts = {"train": len(train), "validation": len(validation), "test": len(test)}
    issues = list(
        f"{name}_split_empty"
        for name in ("train", "validation", "test")
        if counts[name] < selected_config.minimum_records_per_split
    )
    if duplicate_ids:
        issues.append("duplicate_record_ids:" + ",".join(duplicate_ids))
    body = {
        "strategy": selected_config.strategy,
        "seed": selected_config.seed,
        "train_ids": train,
        "validation_ids": validation,
        "test_ids": test,
        "group_assignments": group_assignments,
        "counts": counts,
        "issues": issues,
    }
    return CohortSplit(
        strategy=selected_config.strategy,
        seed=selected_config.seed,
        train_ids=train,
        validation_ids=validation,
        test_ids=test,
        group_assignments=dict(sorted(group_assignments.items())),
        counts=counts,
        issues=tuple(sorted(issues)),
        content_address=content_hash(body, prefix="cohort-split"),
    )


@dataclass(frozen=True, slots=True)
class LeakagePolicy:
    """Explicit policy for cross-split integrity checks."""

    error_on_duplicate_id: bool = True
    error_on_lineage_overlap: bool = True
    error_on_source_overlap: bool = False
    error_on_context_overlap: bool = False
    require_temporal_order: bool = True

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LeakageFinding:
    code: str
    severity: LeakageSeverity
    record_ids: tuple[str, ...]
    splits: tuple[str, ...]
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LeakageReport:
    policy: LeakagePolicy
    findings: tuple[LeakageFinding, ...]
    duplicate_id_count: int
    lineage_overlap_count: int
    source_overlap_count: int
    context_overlap_count: int
    temporal_violation_count: int
    state: BenchmarkState
    content_address: str

    @property
    def accepted(self) -> bool:
        return self.state is BenchmarkState.ACCEPTED

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted": self.accepted}


def _finding(
    code: str,
    severity: LeakageSeverity,
    record_ids: Iterable[str],
    splits: Iterable[str],
    detail: str,
) -> LeakageFinding:
    body = {
        "code": code,
        "severity": severity,
        "record_ids": tuple(sorted(set(record_ids))),
        "splits": tuple(sorted(set(splits))),
        "detail": detail,
    }
    return LeakageFinding(
        code=code,
        severity=severity,
        record_ids=body["record_ids"],
        splits=body["splits"],
        detail=detail,
        content_address=content_hash(body, prefix="cohort-leakage"),
    )


def audit_cohort_leakage(
    records: Sequence[CohortBenchmarkRecord],
    split: CohortSplit,
    policy: LeakagePolicy | None = None,
) -> LeakageReport:
    """Audit duplicate IDs, lineage, sources, contexts, and temporal order."""

    selected_policy = policy or LeakagePolicy()
    by_id: dict[str, list[CohortBenchmarkRecord]] = {}
    for record in records:
        by_id.setdefault(record.record_id, []).append(record)
    assignment = {
        record_id: split_name
        for split_name in ("train", "validation", "test")
        for record_id in split.ids_for(split_name)
    }
    findings: list[LeakageFinding] = []
    duplicate_ids = [record_id for record_id, values in by_id.items() if len(values) > 1]
    if duplicate_ids:
        findings.append(
            _finding(
                "duplicate_record_id",
                LeakageSeverity.ERROR if selected_policy.error_on_duplicate_id else LeakageSeverity.WARNING,
                duplicate_ids,
                (assignment.get(record_id, "unassigned") for record_id in duplicate_ids),
                "one record identifier appears more than once",
            )
        )

    def cross_split(
        code: str,
        values: Mapping[str, list[CohortBenchmarkRecord]],
        enabled: bool,
        detail: str,
    ) -> int:
        if not enabled:
            return 0
        count = 0
        for key, members in sorted(values.items()):
            splits = tuple(sorted({assignment.get(member.record_id, "unassigned") for member in members}))
            if len(splits) > 1:
                count += 1
                findings.append(
                    _finding(
                        code,
                        LeakageSeverity.ERROR,
                        (member.record_id for member in members),
                        splits,
                        f"{detail}: {key}",
                    )
                )
        return count

    lineage = {}
    for record in records:
        if record.lineage_key:
            lineage.setdefault(record.lineage_key, []).append(record)
    lineage_count = cross_split(
        "lineage_cross_split",
        lineage,
        selected_policy.error_on_lineage_overlap,
        "lineage key spans multiple splits",
    )
    sources: dict[str, list[CohortBenchmarkRecord]] = {}
    for record in records:
        sources.setdefault(record.source_id, []).append(record)
    source_count = cross_split(
        "source_cross_split",
        sources,
        selected_policy.error_on_source_overlap,
        "source is present in multiple splits",
    )
    contexts: dict[str, list[CohortBenchmarkRecord]] = {}
    for record in records:
        contexts.setdefault(record.context_key, []).append(record)
    context_count = cross_split(
        "context_cross_split",
        contexts,
        selected_policy.error_on_context_overlap,
        "context is present in multiple splits",
    )
    temporal_count = 0
    if selected_policy.require_temporal_order and split.strategy is SplitStrategy.TEMPORAL:
        dates_by_split: dict[str, list[datetime]] = {"train": [], "validation": [], "test": []}
        for record in records:
            selected = assignment.get(record.record_id)
            value = _parse_datetime(record.collected_at)
            if selected and value is not None:
                dates_by_split[selected].append(value)
        train_max = max(dates_by_split["train"], default=None)
        validation_min = min(dates_by_split["validation"], default=None)
        test_min = min(dates_by_split["test"], default=None)
        if train_max and validation_min and train_max > validation_min:
            temporal_count += 1
            findings.append(
                _finding(
                    "temporal_order_violation",
                    LeakageSeverity.ERROR,
                    split.train_ids + split.validation_ids,
                    ("train", "validation"),
                    "training data extends beyond the validation start",
                )
            )
        if validation_min and test_min and validation_min > test_min:
            temporal_count += 1
            findings.append(
                _finding(
                    "temporal_order_violation",
                    LeakageSeverity.ERROR,
                    split.validation_ids + split.test_ids,
                    ("validation", "test"),
                    "validation data extends beyond the test start",
                )
            )
    if split.issues:
        findings.append(
            _finding(
                "split_contract",
                LeakageSeverity.ERROR,
                record_ids=tuple(record.record_id for record in records),
                splits=("train", "validation", "test"),
                detail="split construction reported: " + "; ".join(split.issues),
            )
        )
    state = BenchmarkState.ACCEPTED
    if any(item.severity is LeakageSeverity.ERROR for item in findings):
        state = BenchmarkState.BLOCKED
    elif findings:
        state = BenchmarkState.REVIEW
    body = {
        "policy": selected_policy,
        "findings": findings,
        "duplicate_id_count": len(duplicate_ids),
        "lineage_overlap_count": lineage_count,
        "source_overlap_count": source_count,
        "context_overlap_count": context_count,
        "temporal_violation_count": temporal_count,
        "state": state,
    }
    return LeakageReport(
        policy=selected_policy,
        findings=tuple(findings),
        duplicate_id_count=len(duplicate_ids),
        lineage_overlap_count=lineage_count,
        source_overlap_count=source_count,
        context_overlap_count=context_count,
        temporal_violation_count=temporal_count,
        state=state,
        content_address=content_hash(body, prefix="cohort-leakage-report"),
    )


@dataclass(frozen=True, slots=True)
class CalibrationConfig:
    """Thresholds for descriptive held-out calibration checks."""

    bins: int = 10
    minimum_records: int = 5
    maximum_ece: float = 0.15
    maximum_mce: float = 0.25
    maximum_brier: float = 0.25

    def __post_init__(self) -> None:
        if self.bins < 2 or self.bins > COHORT_BENCHMARK_MAX_BINS:
            raise ValidationError("calibration bins must be between 2 and 100")
        if self.minimum_records < 1:
            raise ValidationError("calibration minimum_records must be positive")
        for name in ("maximum_ece", "maximum_mce", "maximum_brier"):
            object.__setattr__(self, name, _bounded(getattr(self, name), name))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CalibrationBin:
    bin_index: int
    lower: float
    upper: float
    count: int
    mean_score: float
    observed_rate: float
    absolute_gap: float
    brier_contribution: float
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CalibrationReport:
    config: CalibrationConfig
    record_count: int
    usable_count: int
    missing_label_count: int
    missing_score_count: int
    bins: tuple[CalibrationBin, ...]
    brier_score: float
    log_loss: float
    expected_calibration_error: float
    maximum_calibration_error: float
    calibration_slope: float | None
    calibration_intercept: float | None
    state: BenchmarkState
    content_address: str

    @property
    def accepted(self) -> bool:
        return self.state is BenchmarkState.ACCEPTED

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted": self.accepted}


def benchmark_calibration(
    records: Sequence[CohortBenchmarkRecord],
    config: CalibrationConfig | None = None,
) -> CalibrationReport:
    """Compute reliability, Brier, log-loss, and slope metrics on held-out rows."""

    selected_config = config or CalibrationConfig()
    missing_label = sum(record.label is None for record in records)
    missing_score = sum(record.score is None for record in records)
    usable = tuple(
        record for record in records if record.label is not None and record.score is not None
    )
    bins: list[CalibrationBin] = []
    by_bin: dict[int, list[CohortBenchmarkRecord]] = {}
    for record in usable:
        index = min(int(record.score * selected_config.bins), selected_config.bins - 1)
        by_bin.setdefault(index, []).append(record)
    for index in sorted(by_bin):
        members = by_bin[index]
        mean_score = sum(record.score or 0.0 for record in members) / len(members)
        observed = sum(record.label or 0 for record in members) / len(members)
        gap = abs(mean_score - observed)
        brier = sum(((record.score or 0.0) - (record.label or 0)) ** 2 for record in members) / len(members)
        body = {
            "bin_index": index,
            "lower": index / selected_config.bins,
            "upper": (index + 1) / selected_config.bins,
            "count": len(members),
            "mean_score": round(mean_score, 6),
            "observed_rate": round(observed, 6),
            "absolute_gap": round(gap, 6),
            "brier_contribution": round(brier, 6),
        }
        bins.append(
            CalibrationBin(
                bin_index=index,
                lower=body["lower"],
                upper=body["upper"],
                count=len(members),
                mean_score=body["mean_score"],
                observed_rate=body["observed_rate"],
                absolute_gap=body["absolute_gap"],
                brier_contribution=body["brier_contribution"],
                content_address=content_hash(body, prefix="calibration-bin"),
            )
        )
    count = len(usable)
    brier_score = (
        sum(((record.score or 0.0) - (record.label or 0)) ** 2 for record in usable) / count
        if count
        else 0.0
    )
    epsilon = 1e-12
    log_loss = (
        -sum(
            (record.label or 0) * log(max(record.score or 0.0, epsilon))
            + (1 - (record.label or 0)) * log(max(1 - (record.score or 0.0), epsilon))
            for record in usable
        )
        / count
        if count
        else 0.0
    )
    ece = sum(item.count / max(1, count) * item.absolute_gap for item in bins)
    mce = max((item.absolute_gap for item in bins), default=0.0)
    mean_score = sum(record.score or 0.0 for record in usable) / max(1, count)
    mean_label = sum(record.label or 0 for record in usable) / max(1, count)
    denominator = sum(((record.score or 0.0) - mean_score) ** 2 for record in usable)
    covariance = sum(
        ((record.score or 0.0) - mean_score) * ((record.label or 0) - mean_label)
        for record in usable
    )
    slope = round(covariance / denominator, 6) if denominator else None
    intercept = round(mean_label - (slope or 0.0) * mean_score, 6) if slope is not None else None
    state = BenchmarkState.ACCEPTED
    if count < selected_config.minimum_records:
        state = BenchmarkState.ABSTAINED
    elif (
        ece > selected_config.maximum_ece
        or mce > selected_config.maximum_mce
        or brier_score > selected_config.maximum_brier
    ):
        state = BenchmarkState.REVIEW
    body = {
        "config": selected_config,
        "record_count": len(records),
        "usable_count": count,
        "missing_label_count": missing_label,
        "missing_score_count": missing_score,
        "bins": bins,
        "brier_score": round(brier_score, 6),
        "log_loss": round(log_loss, 6),
        "expected_calibration_error": round(ece, 6),
        "maximum_calibration_error": round(mce, 6),
        "calibration_slope": slope,
        "calibration_intercept": intercept,
        "state": state,
    }
    return CalibrationReport(
        config=selected_config,
        record_count=len(records),
        usable_count=count,
        missing_label_count=missing_label,
        missing_score_count=missing_score,
        bins=tuple(bins),
        brier_score=round(brier_score, 6),
        log_loss=round(log_loss, 6),
        expected_calibration_error=round(ece, 6),
        maximum_calibration_error=round(mce, 6),
        calibration_slope=slope,
        calibration_intercept=intercept,
        state=state,
        content_address=content_hash(body, prefix="calibration-report"),
    )


@dataclass(frozen=True, slots=True)
class SelectiveRiskConfig:
    """Threshold policy for held-out risk-coverage analysis."""

    minimum_coverage: float = 0.5
    maximum_risk: float = 0.25
    maximum_uncertainty: float = 0.25
    points: int = 21
    minimum_records: int = 5

    def __post_init__(self) -> None:
        object.__setattr__(self, "minimum_coverage", _bounded(self.minimum_coverage, "minimum_coverage"))
        object.__setattr__(self, "maximum_risk", _bounded(self.maximum_risk, "maximum_risk"))
        object.__setattr__(self, "maximum_uncertainty", _non_negative(self.maximum_uncertainty, "maximum_uncertainty"))
        if self.points < 2 or self.points > COHORT_BENCHMARK_MAX_POINTS:
            raise ValidationError("selective-risk points must be between 2 and 101")
        if self.minimum_records < 1:
            raise ValidationError("selective-risk minimum_records must be positive")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SelectiveRiskPoint:
    threshold: float
    accepted_count: int
    coverage: float
    error_count: int
    risk: float
    abstention_rate: float
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SelectiveRiskReport:
    config: SelectiveRiskConfig
    record_count: int
    usable_count: int
    points: tuple[SelectiveRiskPoint, ...]
    best_threshold: float | None
    best_coverage: float
    best_risk: float | None
    area_under_risk_coverage: float
    state: BenchmarkState
    content_address: str

    @property
    def accepted(self) -> bool:
        return self.state is BenchmarkState.ACCEPTED

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted": self.accepted}


def benchmark_selective_risk(
    records: Sequence[CohortBenchmarkRecord],
    config: SelectiveRiskConfig | None = None,
) -> SelectiveRiskReport:
    """Build a deterministic risk-coverage curve with uncertainty abstention."""

    selected_config = config or SelectiveRiskConfig()
    usable = tuple(
        record for record in records if record.label is not None and record.score is not None
    )
    thresholds = tuple(
        round(index / (selected_config.points - 1), 6)
        for index in range(selected_config.points)
    )
    points: list[SelectiveRiskPoint] = []
    for threshold in thresholds:
        accepted = tuple(
            record
            for record in usable
            if max(record.score or 0.0, 1.0 - (record.score or 0.0)) >= threshold
            and record.uncertainty <= selected_config.maximum_uncertainty
        )
        errors = sum(int(((record.score or 0.0) >= 0.5) != bool(record.label)) for record in accepted)
        coverage = len(accepted) / max(1, len(usable))
        risk = errors / max(1, len(accepted))
        body = {
            "threshold": threshold,
            "accepted_count": len(accepted),
            "coverage": round(coverage, 6),
            "error_count": errors,
            "risk": round(risk, 6),
            "abstention_rate": round(1.0 - coverage, 6),
        }
        points.append(
            SelectiveRiskPoint(
                threshold=threshold,
                accepted_count=len(accepted),
                coverage=body["coverage"],
                error_count=errors,
                risk=body["risk"],
                abstention_rate=body["abstention_rate"],
                content_address=content_hash(body, prefix="selective-risk-point"),
            )
        )
    candidates = tuple(
        point
        for point in points
        if point.coverage >= selected_config.minimum_coverage
        and point.risk <= selected_config.maximum_risk
    )
    best = max(candidates, key=lambda point: (point.coverage, -point.risk, -point.threshold), default=None)
    ordered = sorted(points, key=lambda point: point.coverage)
    aurc = 0.0
    for left, right in zip(ordered, ordered[1:], strict=False):
        aurc += (right.coverage - left.coverage) * (left.risk + right.risk) / 2.0
    if not usable:
        state = BenchmarkState.ABSTAINED
    elif len(usable) < selected_config.minimum_records:
        state = BenchmarkState.ABSTAINED
    elif best is None:
        state = BenchmarkState.REVIEW
    else:
        state = BenchmarkState.ACCEPTED
    body = {
        "config": selected_config,
        "record_count": len(records),
        "usable_count": len(usable),
        "points": points,
        "best_threshold": best.threshold if best else None,
        "best_coverage": best.coverage if best else 0.0,
        "best_risk": best.risk if best else None,
        "area_under_risk_coverage": round(aurc, 6),
        "state": state,
    }
    return SelectiveRiskReport(
        config=selected_config,
        record_count=len(records),
        usable_count=len(usable),
        points=tuple(points),
        best_threshold=best.threshold if best else None,
        best_coverage=best.coverage if best else 0.0,
        best_risk=best.risk if best else None,
        area_under_risk_coverage=round(aurc, 6),
        state=state,
        content_address=content_hash(body, prefix="selective-risk-report"),
    )


@dataclass(frozen=True, slots=True)
class TransportConfig:
    """Declared source-to-target transport thresholds."""

    minimum_feature_overlap: float = 0.75
    maximum_positive_rate_shift: float = 0.2
    maximum_score_shift: float = 0.2
    maximum_brier_shift: float = 0.15
    minimum_records_per_domain: int = 2

    def __post_init__(self) -> None:
        for name in (
            "minimum_feature_overlap",
            "maximum_positive_rate_shift",
            "maximum_score_shift",
            "maximum_brier_shift",
        ):
            object.__setattr__(self, name, _bounded(getattr(self, name), name))
        if self.minimum_records_per_domain < 1:
            raise ValidationError("minimum_records_per_domain must be positive")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TransportDomainSummary:
    domain_id: str
    record_count: int
    source_ids: tuple[str, ...]
    context_keys: tuple[str, ...]
    feature_keys: tuple[str, ...]
    positive_rate: float | None
    mean_score: float | None
    brier_score: float | None
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TransportPair:
    source_domain: str
    target_domain: str
    feature_overlap: float
    positive_rate_shift: float | None
    score_shift: float | None
    brier_shift: float | None
    state: BenchmarkState
    issues: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TransportReport:
    config: TransportConfig
    source_domain: str
    source: TransportDomainSummary | None
    targets: tuple[TransportDomainSummary, ...]
    pairs: tuple[TransportPair, ...]
    accepted_domains: tuple[str, ...]
    review_domains: tuple[str, ...]
    state: BenchmarkState
    content_address: str

    @property
    def accepted(self) -> bool:
        return self.state is BenchmarkState.ACCEPTED

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted": self.accepted}


def _domain_summary(domain_id: str, records: Sequence[CohortBenchmarkRecord]) -> TransportDomainSummary:
    usable_labels = tuple(record for record in records if record.label is not None)
    usable_scores = tuple(record for record in records if record.score is not None)
    paired = tuple(
        record for record in records if record.label is not None and record.score is not None
    )
    positive_rate = (
        sum(record.label or 0 for record in usable_labels) / len(usable_labels)
        if usable_labels
        else None
    )
    mean_score = (
        sum(record.score or 0.0 for record in usable_scores) / len(usable_scores)
        if usable_scores
        else None
    )
    brier = (
        sum(((record.score or 0.0) - (record.label or 0)) ** 2 for record in paired) / len(paired)
        if paired
        else None
    )
    body = {
        "domain_id": domain_id,
        "record_count": len(records),
        "source_ids": _unique_texts(record.source_id for record in records),
        "context_keys": _unique_texts(record.context_key for record in records),
        "feature_keys": _unique_texts(
            feature for record in records for feature in record.feature_keys
        ),
        "positive_rate": None if positive_rate is None else round(positive_rate, 6),
        "mean_score": None if mean_score is None else round(mean_score, 6),
        "brier_score": None if brier is None else round(brier, 6),
    }
    return TransportDomainSummary(
        domain_id=domain_id,
        record_count=len(records),
        source_ids=body["source_ids"],
        context_keys=body["context_keys"],
        feature_keys=body["feature_keys"],
        positive_rate=body["positive_rate"],
        mean_score=body["mean_score"],
        brier_score=body["brier_score"],
        content_address=content_hash(body, prefix="transport-domain"),
    )


def benchmark_transport(
    records: Sequence[CohortBenchmarkRecord],
    *,
    source_domain: str,
    target_domains: Sequence[str] | None = None,
    config: TransportConfig | None = None,
) -> TransportReport:
    """Compare declared source and target domains without asserting transportability."""

    source_domain = _text(source_domain, "source_domain")
    selected_config = config or TransportConfig()
    by_domain: dict[str, list[CohortBenchmarkRecord]] = {}
    for record in records:
        by_domain.setdefault(record.domain_id, []).append(record)
    if len(by_domain) > COHORT_BENCHMARK_MAX_DOMAINS:
        raise ValidationError("transport domain ceiling was exceeded")
    source = (
        _domain_summary(source_domain, by_domain[source_domain])
        if source_domain in by_domain
        else None
    )
    selected_targets = tuple(
        sorted(
            set(target_domains or tuple(domain for domain in by_domain if domain != source_domain))
            - {source_domain}
        )
    )
    targets = tuple(
        _domain_summary(domain, by_domain[domain])
        for domain in selected_targets
        if domain in by_domain
    )
    pairs: list[TransportPair] = []
    for target in targets:
        issues: list[str] = []
        if source is None:
            issues.append("source_domain_missing")
        if target.record_count < selected_config.minimum_records_per_domain:
            issues.append("target_domain_small")
        if source is not None and source.record_count < selected_config.minimum_records_per_domain:
            issues.append("source_domain_small")
        source_features = set(source.feature_keys if source else ())
        target_features = set(target.feature_keys)
        overlap = len(source_features & target_features) / max(1, len(target_features))
        if overlap < selected_config.minimum_feature_overlap:
            issues.append("feature_overlap_low")
        positive_shift = (
            None
            if source is None or source.positive_rate is None or target.positive_rate is None
            else abs(source.positive_rate - target.positive_rate)
        )
        score_shift = (
            None
            if source is None or source.mean_score is None or target.mean_score is None
            else abs(source.mean_score - target.mean_score)
        )
        brier_shift = (
            None
            if source is None or source.brier_score is None or target.brier_score is None
            else abs(source.brier_score - target.brier_score)
        )
        if positive_shift is None:
            issues.append("positive_rate_missing")
        elif positive_shift > selected_config.maximum_positive_rate_shift:
            issues.append("positive_rate_shift_high")
        if score_shift is None:
            issues.append("score_missing")
        elif score_shift > selected_config.maximum_score_shift:
            issues.append("score_shift_high")
        if brier_shift is None:
            issues.append("brier_missing")
        elif brier_shift > selected_config.maximum_brier_shift:
            issues.append("brier_shift_high")
        state = BenchmarkState.ACCEPTED if not issues else BenchmarkState.REVIEW
        body = {
            "source_domain": source_domain,
            "target_domain": target.domain_id,
            "feature_overlap": round(overlap, 6),
            "positive_rate_shift": positive_shift,
            "score_shift": score_shift,
            "brier_shift": brier_shift,
            "state": state,
            "issues": tuple(sorted(issues)),
        }
        pairs.append(
            TransportPair(
                source_domain=source_domain,
                target_domain=target.domain_id,
                feature_overlap=body["feature_overlap"],
                positive_rate_shift=(
                    None
                    if positive_shift is None
                    else round(positive_shift, 6)
                ),
                score_shift=None if score_shift is None else round(score_shift, 6),
                brier_shift=None if brier_shift is None else round(brier_shift, 6),
                state=state,
                issues=tuple(sorted(issues)),
                content_address=content_hash(body, prefix="transport-pair"),
            )
        )
    accepted_domains = tuple(item.target_domain for item in pairs if item.state is BenchmarkState.ACCEPTED)
    review_domains = tuple(item.target_domain for item in pairs if item.state is not BenchmarkState.ACCEPTED)
    if source is None or not targets:
        state = BenchmarkState.ABSTAINED
    elif all(item.state is BenchmarkState.ACCEPTED for item in pairs):
        state = BenchmarkState.ACCEPTED
    else:
        state = BenchmarkState.REVIEW
    body = {
        "config": selected_config,
        "source_domain": source_domain,
        "source": source,
        "targets": targets,
        "pairs": pairs,
        "accepted_domains": accepted_domains,
        "review_domains": review_domains,
        "state": state,
    }
    return TransportReport(
        config=selected_config,
        source_domain=source_domain,
        source=source,
        targets=targets,
        pairs=tuple(pairs),
        accepted_domains=accepted_domains,
        review_domains=review_domains,
        state=state,
        content_address=content_hash(body, prefix="transport-report"),
    )


@dataclass(frozen=True, slots=True)
class CohortBenchmarkConfig:
    """Master suite configuration tying every benchmark plane together."""

    split: SplitConfig = SplitConfig()
    leakage: LeakagePolicy = LeakagePolicy()
    calibration: CalibrationConfig = CalibrationConfig()
    selective_risk: SelectiveRiskConfig = SelectiveRiskConfig()
    transport: TransportConfig = TransportConfig()
    evaluation_split: str = "test"
    transport_split: str = "all"
    source_domain: str | None = None
    target_domains: tuple[str, ...] = ()
    max_records: int = COHORT_BENCHMARK_MAX_RECORDS

    def __post_init__(self) -> None:
        _text(self.evaluation_split, "evaluation_split")
        _text(self.transport_split, "transport_split")
        if self.max_records < 1 or self.max_records > COHORT_BENCHMARK_MAX_RECORDS:
            raise ValidationError("benchmark max_records is outside the configured ceiling")
        if self.source_domain is not None and not str(self.source_domain).strip():
            object.__setattr__(self, "source_domain", None)
        object.__setattr__(self, "target_domains", _unique_texts(self.target_domains))

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any] | None) -> "CohortBenchmarkConfig":
        value = raw or {}
        return cls(
            split=SplitConfig.from_mapping(value.get("split")),
            leakage=LeakagePolicy(**dict(value.get("leakage", {}))),
            calibration=CalibrationConfig(**dict(value.get("calibration", {}))),
            selective_risk=SelectiveRiskConfig(**dict(value.get("selective_risk", {}))),
            transport=TransportConfig(**dict(value.get("transport", {}))),
            evaluation_split=str(value.get("evaluation_split", "test")),
            transport_split=str(value.get("transport_split", "all")),
            source_domain=(
                None if value.get("source_domain") is None else str(value.get("source_domain"))
            ),
            target_domains=_as_text_tuple(value.get("target_domains", ())),
            max_records=int(value.get("max_records", COHORT_BENCHMARK_MAX_RECORDS)),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortBenchmarkReport:
    """Complete addressed benchmark receipt across all requested planes."""

    dataset_id: str
    version: str
    record_count: int
    split: CohortSplit
    leakage: LeakageReport
    evaluation_split: str
    evaluation_record_count: int
    transport_split: str
    calibration: CalibrationReport
    selective_risk: SelectiveRiskReport
    transport: TransportReport
    state: BenchmarkState
    warnings: tuple[str, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return self.state is BenchmarkState.ACCEPTED

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted": self.accepted}


def run_cohort_benchmark(
    records: Iterable[CohortBenchmarkRecord | Mapping[str, Any]],
    *,
    dataset_id: str = "cohort-benchmark",
    config: CohortBenchmarkConfig | None = None,
) -> CohortBenchmarkReport:
    """Run split, leakage, held-out calibration/risk, and transport checks."""

    dataset_id = _text(dataset_id, "dataset_id")
    selected_config = config or CohortBenchmarkConfig()
    normalized = tuple(
        record
        if isinstance(record, CohortBenchmarkRecord)
        else CohortBenchmarkRecord.from_mapping(record)
        for record in records
    )
    if not normalized:
        raise ValidationError("cohort benchmark requires at least one record")
    if len(normalized) > selected_config.max_records:
        raise ValidationError("cohort benchmark input exceeds max_records")
    split = build_cohort_split(normalized, selected_config.split)
    leakage = audit_cohort_leakage(normalized, split, selected_config.leakage)
    selected_ids = set(split.ids_for(selected_config.evaluation_split))
    evaluation = tuple(record for record in normalized if record.record_id in selected_ids)
    calibration = benchmark_calibration(evaluation, selected_config.calibration)
    selective = benchmark_selective_risk(evaluation, selected_config.selective_risk)
    source_domain = selected_config.source_domain
    if source_domain is None:
        source_domain = sorted({record.domain_id for record in evaluation})[0] if evaluation else ""
    transport_records = (
        normalized
        if selected_config.transport_split.casefold() == "all"
        else tuple(
            record
            for record in normalized
            if record.record_id in set(split.ids_for(selected_config.transport_split))
        )
    )
    transport = benchmark_transport(
        transport_records,
        source_domain=source_domain,
        target_domains=selected_config.target_domains or None,
        config=selected_config.transport,
    )
    warnings: list[str] = [
        "benchmark metrics are descriptive and require external validation before performance claims",
        "aggregate records are not a patient-level cohort",
    ]
    if calibration.state is BenchmarkState.ABSTAINED:
        warnings.append("calibration abstained because held-out labels or scores were insufficient")
    if selective.state is BenchmarkState.ABSTAINED:
        warnings.append("selective-risk abstained because held-out labels or scores were insufficient")
    if transport.state is BenchmarkState.ABSTAINED:
        warnings.append("transport benchmark abstained because source or target domains were missing")
    if leakage.state is BenchmarkState.BLOCKED:
        warnings.append("leakage findings block benchmark acceptance")
    states = (leakage.state, calibration.state, selective.state, transport.state)
    if leakage.state is BenchmarkState.BLOCKED:
        state = BenchmarkState.BLOCKED
    elif any(item is BenchmarkState.ABSTAINED for item in states):
        state = BenchmarkState.ABSTAINED
    elif all(item is BenchmarkState.ACCEPTED for item in states):
        state = BenchmarkState.ACCEPTED
    else:
        state = BenchmarkState.REVIEW
    body = {
        "dataset_id": dataset_id,
        "version": COHORT_BENCHMARK_VERSION,
        "record_count": len(normalized),
        "split": split,
        "leakage": leakage,
        "evaluation_split": selected_config.evaluation_split,
        "evaluation_record_count": len(evaluation),
        "transport_split": selected_config.transport_split,
        "calibration": calibration,
        "selective_risk": selective,
        "transport": transport,
        "state": state,
        "warnings": tuple(dict.fromkeys(warnings)),
    }
    return CohortBenchmarkReport(
        dataset_id=dataset_id,
        version=COHORT_BENCHMARK_VERSION,
        record_count=len(normalized),
        split=split,
        leakage=leakage,
        evaluation_split=selected_config.evaluation_split,
        evaluation_record_count=len(evaluation),
        transport_split=selected_config.transport_split,
        calibration=calibration,
        selective_risk=selective,
        transport=transport,
        state=state,
        warnings=tuple(dict.fromkeys(warnings)),
        content_address=content_hash(body, prefix="cohort-benchmark-report"),
    )


def load_cohort_benchmark_records(path: str | Path) -> tuple[Mapping[str, Any], ...]:
    """Load aggregate benchmark rows from JSON, JSONL, CSV, or TSV."""

    source = Path(path)
    suffix = source.suffix.casefold()
    if suffix == ".jsonl":
        rows: list[Mapping[str, Any]] = []
        for line_number, line in enumerate(
            source.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, Mapping):
                raise ValidationError(f"JSONL benchmark row {line_number} must be an object")
            rows.append(value)
        return tuple(rows)
    if suffix == ".json":
        value = json.loads(source.read_text(encoding="utf-8"))
        if isinstance(value, Mapping):
            value = value.get("records", value.get("rows", ()))
        if not isinstance(value, list) or not all(isinstance(row, Mapping) for row in value):
            raise ValidationError("JSON benchmark input must be a list of objects")
        return tuple(value)
    delimiter = "\t" if suffix == ".tsv" else ","
    reader = csv.DictReader(io.StringIO(source.read_text(encoding="utf-8")), delimiter=delimiter)
    if not reader.fieldnames:
        raise ValidationError("delimited benchmark input requires a header")
    return tuple(dict(row) for row in reader)


def cohort_benchmark_schema() -> dict[str, Any]:
    """Return the machine-readable suite contract."""

    return {
        "version": COHORT_BENCHMARK_SCHEMA_VERSION,
        "benchmark_version": COHORT_BENCHMARK_VERSION,
        "record_fields": [
            "record_id",
            "cohort_id",
            "domain_id",
            "source_id",
            "context_key",
            "label",
            "score",
            "uncertainty",
            "group_id",
            "lineage_key",
            "feature_keys",
            "collected_at",
            "tags",
        ],
        "split_strategies": [item.value for item in SplitStrategy],
        "states": [item.value for item in BenchmarkState],
        "leakage_severities": [item.value for item in LeakageSeverity],
        "limits": {
            "max_records": COHORT_BENCHMARK_MAX_RECORDS,
            "max_bins": COHORT_BENCHMARK_MAX_BINS,
            "max_points": COHORT_BENCHMARK_MAX_POINTS,
            "max_domains": COHORT_BENCHMARK_MAX_DOMAINS,
        },
        "metrics": [
            "expected_calibration_error",
            "maximum_calibration_error",
            "brier_score",
            "log_loss",
            "calibration_slope",
            "calibration_intercept",
            "risk_coverage_curve",
            "area_under_risk_coverage",
            "feature_overlap",
            "positive_rate_shift",
            "score_shift",
            "brier_shift",
        ],
        "public_boundary": [
            "direct subject, sample, contact, credential, model, agent, and language fields are rejected",
            "benchmark outputs are aggregate and source/context addressed",
            "metrics are descriptive and not external validation",
            "leakage errors block acceptance",
            "insufficient evidence abstains rather than producing a negative",
        ],
    }


def cohort_benchmark_capabilities() -> dict[str, Any]:
    """Describe operational benchmark behavior without source rows."""

    return {
        "version": COHORT_BENCHMARK_VERSION,
        "split": {
            "strategies": [item.value for item in SplitStrategy],
            "grouped_strategies_keep_group_keys_together": True,
            "temporal_strategy_requires_collected_at": True,
            "seeded_hash_assignment_is_deterministic": True,
        },
        "leakage": {
            "checks": [
                "duplicate_record_id",
                "lineage_cross_split",
                "source_cross_split",
                "context_cross_split",
                "temporal_order_violation",
            ],
            "errors_block_acceptance": True,
        },
        "calibration": {
            "metrics": ["brier_score", "log_loss", "expected_calibration_error", "maximum_calibration_error"],
            "held_out_only": True,
            "no_truth_set_means_abstention": True,
        },
        "selective_risk": {
            "metrics": ["coverage", "risk", "abstention_rate", "area_under_risk_coverage"],
            "uncertainty_gate_is_explicit": True,
        },
        "transport": {
            "metrics": ["feature_overlap", "positive_rate_shift", "score_shift", "brier_shift"],
            "transportability_is_never_inferred_from_overlap_alone": True,
        },
        "limits": cohort_benchmark_schema()["limits"],
    }


__all__ = [
    "BenchmarkState",
    "CalibrationBin",
    "CalibrationConfig",
    "CalibrationReport",
    "COHORT_BENCHMARK_MAX_BINS",
    "COHORT_BENCHMARK_MAX_DOMAINS",
    "COHORT_BENCHMARK_MAX_POINTS",
    "COHORT_BENCHMARK_MAX_RECORDS",
    "COHORT_BENCHMARK_RECORD_SCHEMA_VERSION",
    "COHORT_BENCHMARK_SCHEMA_VERSION",
    "COHORT_BENCHMARK_VERSION",
    "CohortBenchmarkConfig",
    "CohortBenchmarkRecord",
    "CohortBenchmarkReport",
    "CohortSplit",
    "LeakageFinding",
    "LeakagePolicy",
    "LeakageReport",
    "LeakageSeverity",
    "SelectiveRiskConfig",
    "SelectiveRiskPoint",
    "SelectiveRiskReport",
    "SplitConfig",
    "SplitStrategy",
    "TransportConfig",
    "TransportDomainSummary",
    "TransportPair",
    "TransportReport",
    "audit_cohort_leakage",
    "benchmark_calibration",
    "benchmark_selective_risk",
    "benchmark_transport",
    "build_cohort_split",
    "cohort_benchmark_capabilities",
    "cohort_benchmark_schema",
    "load_cohort_benchmark_records",
    "run_cohort_benchmark",
]
