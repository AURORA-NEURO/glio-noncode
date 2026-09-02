"""Typed in-memory case preparation and execution.

This module is the small, fail-closed facade over variant intake, regulatory
track intake, ``CaseManifest``, and ``CaseRuntime``.  Source payloads are
always supplied by the caller; this boundary never resolves a server-local
path.  Observational timestamps are retained on stage receipts but are
deliberately excluded from every scientific content address.
"""

from __future__ import annotations

import base64
import math
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from itertools import islice
from pathlib import Path
from typing import Any

from .errors import GlioError, ValidationError
from .expression_evidence import (
    SCHEMA_VERSION as EXPRESSION_EVIDENCE_SCHEMA_VERSION,
)
from .expression_evidence import (
    AllelicDirection,
    ExpressionDirection,
    RegulatoryDirection,
    RNAConsequenceEvidence,
    RNAEvidenceState,
)
from .intake import (
    MAX_VARIANT_INTAKE_AUXILIARY_LINES,
    MAX_VARIANT_INTAKE_RECORDS,
    IntakeBatch,
    IntakeFormat,
    IntakeSeverity,
    VariantIntake,
)
from .models import (
    CandidateElement,
    CaseManifest,
    Dossier,
    ReferenceContext,
    ResearchStatus,
    VariantIdentity,
    VariantKind,
    VariantOrigin,
)
from .regulatory_tracks import (
    MAX_REGULATORY_TRACK_AUXILIARY_LINES,
    MAX_REGULATORY_TRACK_RECORDS,
    RegulatoryTrackBatch,
    RegulatoryTrackFormat,
    RegulatoryTrackParser,
    TrackIssueSeverity,
)
from .replay import ReplayReport, ReplayVerifier
from .runtime import CaseRuntime
from .serialization import content_hash, hash_bytes, jsonable, utc_now
from .storage import MAX_RUN_HISTORY_ENTRIES

WORKFLOW_VERSION = "case-workflow-v1"
MAX_CASE_RNA_CONSEQUENCES = 10_000
MAX_CASE_REGULATORY_TRACKS = 1_000
MAX_CASE_CANDIDATE_ELEMENTS = MAX_REGULATORY_TRACK_RECORDS
MAX_CASE_TARGET_GENE_KEYS = 32
MAX_CASE_TARGET_GENE_KEY_LENGTH = 128
MAX_CASE_TARGETS_PER_ELEMENT = 128
MAX_CASE_RUNTIME_WORK_ITEMS = 10_000
_CONTEXT_FIELDS = {
    "genome_build",
    "disease_class",
    "age_group",
    "cell_state",
    "territory",
    "treatment_phase",
    "assay_support",
    "source_version",
}
_CONTEXT_REQUIRED_FIELDS = {
    "genome_build",
    "disease_class",
    "age_group",
    "cell_state",
}
_RESERVED_CASE_METADATA_KEYS = {"case_workflow_provenance"}
_MANIFEST_FIELDS = {
    "case_id",
    "subject_id",
    "context",
    "variants",
    "candidate_elements",
    "metadata",
    "input_versions",
    "requested_by",
}
_VARIANT_FIELDS = {
    "variant_id",
    "kind",
    "chromosome",
    "start",
    "end",
    "reference",
    "alternate",
    "genome_build",
    "origin",
    "clonality",
    "sample_id",
    "annotations",
}
_ELEMENT_FIELDS = {
    "element_id",
    "chromosome",
    "start",
    "end",
    "element_type",
    "context",
    "source_id",
    "target_genes",
    "state_ids",
    "features",
    "annotations",
}
_DOSSIER_FIELDS = {
    "dossier_id",
    "case_id",
    "run_id",
    "created_at",
    "input_address",
    "hypotheses",
    "evidence",
    "experiments",
    "review",
    "research_use_only",
    "policy_version",
    "event_head",
    "content_address",
    "status",
    "warnings",
    "source_receipts",
    "source_bundle_addresses",
}
_RUN_RECORD_FIELDS = {
    "run_id",
    "input_address",
    "event_address",
    "event_history",
    "dossier_address",
    "dossier_history",
}
_RNA_CONSEQUENCE_FIELDS = {
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
_RNA_CONSEQUENCE_REQUIRED_FIELDS = _RNA_CONSEQUENCE_FIELDS - {"content_address"}


class WorkflowState(StrEnum):
    """Fail-closed outcome shared by preparation and execution."""

    ACCEPTED = "accepted"
    BLOCKED = "blocked"


class WorkflowSeverity(StrEnum):
    WARNING = "warning"
    ERROR = "error"


class WorkflowStage(StrEnum):
    VARIANT_INTAKE = "variant_intake"
    REGULATORY_TRACK = "regulatory_track"
    MANIFEST = "manifest"
    CASE_RUNTIME = "case_runtime"


class _FrozenJsonObject(dict[str, Any]):
    """A JSON-serializable mapping that rejects normal mutation paths."""

    @staticmethod
    def _immutable() -> None:
        raise TypeError("canonical metadata is immutable")

    def __setitem__(self, _key: str, _value: Any) -> None:
        self._immutable()

    def __delitem__(self, _key: str) -> None:
        self._immutable()

    def clear(self) -> None:
        self._immutable()

    def pop(self, _key: str, _default: Any = None) -> Any:
        self._immutable()

    def popitem(self) -> tuple[str, Any]:
        self._immutable()

    def setdefault(self, _key: str, _default: Any = None) -> Any:
        self._immutable()

    def update(self, *args: Any, **kwargs: Any) -> None:
        self._immutable()

    def __ior__(self, _other: object) -> _FrozenJsonObject:
        self._immutable()

    def __copy__(self) -> _FrozenJsonObject:
        return self

    def __deepcopy__(self, _memo: dict[int, Any]) -> _FrozenJsonObject:
        return self


class _FrozenJsonArray(list[Any]):
    """A list-compatible JSON array that rejects normal mutation paths."""

    @staticmethod
    def _immutable() -> None:
        raise TypeError("canonical metadata is immutable")

    def __setitem__(self, _key: int | slice, _value: Any) -> None:
        self._immutable()

    def __delitem__(self, _key: int | slice) -> None:
        self._immutable()

    def append(self, _value: Any) -> None:
        self._immutable()

    def clear(self) -> None:
        self._immutable()

    def extend(self, _values: Iterable[Any]) -> None:
        self._immutable()

    def insert(self, _index: int, _value: Any) -> None:
        self._immutable()

    def pop(self, _index: int = -1) -> Any:
        self._immutable()

    def remove(self, _value: Any) -> None:
        self._immutable()

    def reverse(self) -> None:
        self._immutable()

    def sort(self, *, key: Any = None, reverse: bool = False) -> None:
        self._immutable()

    def __iadd__(self, _values: Iterable[Any]) -> _FrozenJsonArray:
        self._immutable()

    def __imul__(self, _count: int) -> _FrozenJsonArray:
        self._immutable()

    def __copy__(self) -> _FrozenJsonArray:
        return self

    def __deepcopy__(self, _memo: dict[int, Any]) -> _FrozenJsonArray:
        return self


def _required_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{label} must be a non-empty string")
    return value.strip()


def _sha256_address(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 71
        or not value.startswith("sha256:")
        or any(character not in "0123456789abcdef" for character in value[7:])
    ):
        raise ValidationError(f"{label} must be a canonical sha256 content address")
    return value


def _run_identifier(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 28
        or not value.startswith("run-")
        or any(character not in "0123456789abcdef" for character in value[4:])
    ):
        raise ValidationError(f"{label} must be a canonical run identifier")
    return value


def _rna_consequence_address(value: object, label: str) -> str:
    prefix = "rna-consequence-evidence:"
    if (
        not isinstance(value, str)
        or len(value) != len(prefix) + 64
        or not value.startswith(prefix)
        or any(character not in "0123456789abcdef" for character in value[len(prefix) :])
    ):
        raise ValidationError(f"{label} must be a canonical RNA consequence address")
    return value


def _strict_mapping(
    raw: Mapping[str, Any],
    *,
    allowed: set[str],
    required: set[str] | frozenset[str] = frozenset(),
    label: str,
) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise ValidationError(f"{label} must be an object")
    if any(not isinstance(key, str) for key in raw):
        raise ValidationError(f"{label} keys must be strings")
    unknown = set(raw) - allowed
    if unknown:
        raise ValidationError(f"{label} contains unknown fields: {sorted(unknown)}")
    missing = required - set(raw)
    if missing:
        raise ValidationError(f"{label} is missing required fields: {sorted(missing)}")
    return dict(raw)


def _sequence(value: object, label: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValidationError(f"{label} must be an array")
    return value


def _canonical_json_value(
    value: object,
    label: str,
    active_containers: set[int],
) -> Any:
    if value is None or type(value) in {str, bool, int}:
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise ValidationError(f"{label} numbers must be finite")
        return value
    if isinstance(value, Mapping):
        marker = id(value)
        if marker in active_containers:
            raise ValidationError(f"{label} must not contain recursive containers")
        if any(type(key) is not str for key in value):
            raise ValidationError(f"{label} object keys must be strings")
        active_containers.add(marker)
        try:
            return _FrozenJsonObject(
                {
                    key: _canonical_json_value(item, f"{label}.{key}", active_containers)
                    for key, item in value.items()
                }
            )
        finally:
            active_containers.remove(marker)
    if isinstance(value, (list, tuple)):
        marker = id(value)
        if marker in active_containers:
            raise ValidationError(f"{label} must not contain recursive containers")
        active_containers.add(marker)
        try:
            return _FrozenJsonArray(
                _canonical_json_value(item, f"{label}[{index}]", active_containers)
                for index, item in enumerate(value)
            )
        finally:
            active_containers.remove(marker)
    raise ValidationError(f"{label} must contain only canonical JSON values")


def _json_mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{label} must be an object")
    try:
        result = _canonical_json_value(value, label, set())
        if not isinstance(result, dict):
            raise ValidationError(f"{label} must be an object")
        content_hash(result)
    except RecursionError as exc:
        raise ValidationError(f"{label} nesting is too deep") from exc
    except (TypeError, ValueError, UnicodeError) as exc:
        raise ValidationError(f"{label} must contain canonical JSON values") from exc
    return result


def _text_sequence(
    value: object,
    label: str,
    *,
    allow_empty: bool,
    max_items: int | None = None,
    max_item_length: int | None = None,
) -> tuple[str, ...]:
    items = _sequence(value, label)
    if max_items is not None and len(items) > max_items:
        raise ValidationError(f"{label} exceeds the maximum of {max_items} items")
    normalized = tuple(_required_text(item, f"{label} item") for item in items)
    if not allow_empty and not normalized:
        raise ValidationError(f"{label} must be a non-empty array")
    if max_item_length is not None and any(len(item) > max_item_length for item in normalized):
        raise ValidationError(f"{label} items must not exceed {max_item_length} characters")
    if len(normalized) != len(set(normalized)):
        raise ValidationError(f"{label} must contain unique strings")
    return normalized


def _text_mapping(value: object, label: str) -> _FrozenJsonObject:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{label} must be an object")
    normalized: dict[str, str] = {}
    for key, item in value.items():
        normalized_key = _required_text(key, f"{label} key")
        if normalized_key in normalized:
            raise ValidationError(f"{label} contains duplicate normalized keys")
        normalized[normalized_key] = _required_text(item, f"{label} value")
    return _FrozenJsonObject(normalized)


def _integer(value: object, label: str) -> int:
    if type(value) is not int:
        raise ValidationError(f"{label} must be an integer")
    return value


def _finite_number(value: object, label: str) -> float:
    if type(value) is int:
        return value
    if type(value) is float and math.isfinite(value):
        return value
    raise ValidationError(f"{label} must be a finite number")


def _context(value: ReferenceContext | Mapping[str, Any], label: str) -> ReferenceContext:
    if isinstance(value, ReferenceContext):
        raw = {
            "genome_build": value.genome_build,
            "disease_class": value.disease_class,
            "age_group": value.age_group,
            "cell_state": value.cell_state,
            "territory": value.territory,
            "treatment_phase": value.treatment_phase,
            "assay_support": value.assay_support,
            "source_version": value.source_version,
        }
    else:
        raw = _strict_mapping(
            value,
            allowed=_CONTEXT_FIELDS,
            required=_CONTEXT_REQUIRED_FIELDS,
            label=label,
        )
    return ReferenceContext(
        genome_build=_required_text(raw["genome_build"], f"{label} genome_build"),
        disease_class=_required_text(raw["disease_class"], f"{label} disease_class"),
        age_group=_required_text(raw["age_group"], f"{label} age_group"),
        cell_state=_required_text(raw["cell_state"], f"{label} cell_state"),
        territory=_required_text(raw.get("territory", "unknown"), f"{label} territory"),
        treatment_phase=_required_text(
            raw.get("treatment_phase", "unknown"),
            f"{label} treatment_phase",
        ),
        assay_support=_text_sequence(
            raw.get("assay_support", ()),
            f"{label} assay_support",
            allow_empty=True,
        ),
        source_version=_required_text(
            raw.get("source_version", "unspecified"),
            f"{label} source_version",
        ),
    )


def _variant_identity(
    value: VariantIdentity | Mapping[str, Any],
    label: str,
) -> VariantIdentity:
    raw_value = value.to_dict() if isinstance(value, VariantIdentity) else value
    raw = _strict_mapping(
        raw_value,
        allowed=_VARIANT_FIELDS,
        required=_VARIANT_FIELDS,
        label=label,
    )
    try:
        kind = VariantKind(_required_text(raw["kind"], f"{label} kind"))
    except ValueError as exc:
        raise ValidationError(f"{label} kind is unsupported") from exc
    try:
        origin = VariantOrigin(_required_text(raw["origin"], f"{label} origin"))
    except ValueError as exc:
        raise ValidationError(f"{label} origin is unsupported") from exc
    return VariantIdentity(
        variant_id=_required_text(raw["variant_id"], f"{label} variant_id"),
        kind=kind,
        chromosome=_required_text(raw["chromosome"], f"{label} chromosome"),
        start=_integer(raw["start"], f"{label} start"),
        end=_integer(raw["end"], f"{label} end"),
        reference=_required_text(raw["reference"], f"{label} reference"),
        alternate=_required_text(raw["alternate"], f"{label} alternate"),
        genome_build=_required_text(raw["genome_build"], f"{label} genome_build"),
        origin=origin,
        clonality=_required_text(raw["clonality"], f"{label} clonality"),
        sample_id=_required_text(raw["sample_id"], f"{label} sample_id"),
        annotations=_json_mapping(raw["annotations"], f"{label} annotations"),
    )


def _candidate_element(
    value: CandidateElement | Mapping[str, Any],
    label: str,
) -> CandidateElement:
    raw_value = value.to_dict() if isinstance(value, CandidateElement) else value
    raw = _strict_mapping(
        raw_value,
        allowed=_ELEMENT_FIELDS,
        required=_ELEMENT_FIELDS,
        label=label,
    )
    features_raw = raw["features"]
    if not isinstance(features_raw, Mapping):
        raise ValidationError(f"{label} features must be an object")
    features: dict[str, float] = {}
    for key, item in features_raw.items():
        normalized_key = _required_text(key, f"{label} feature key")
        if normalized_key in features:
            raise ValidationError(f"{label} features contain duplicate normalized keys")
        features[normalized_key] = _finite_number(item, f"{label} feature {normalized_key}")
    context_raw = raw["context"]
    if not isinstance(context_raw, (ReferenceContext, Mapping)):
        raise ValidationError(f"{label} context must be an object")
    if isinstance(context_raw, Mapping):
        _strict_mapping(
            context_raw,
            allowed=_CONTEXT_FIELDS,
            required=_CONTEXT_FIELDS,
            label=f"{label} context",
        )
    return CandidateElement(
        element_id=_required_text(raw["element_id"], f"{label} element_id"),
        chromosome=_required_text(raw["chromosome"], f"{label} chromosome"),
        start=_integer(raw["start"], f"{label} start"),
        end=_integer(raw["end"], f"{label} end"),
        element_type=_required_text(raw["element_type"], f"{label} element_type"),
        context=_context(context_raw, f"{label} context"),
        source_id=_required_text(raw["source_id"], f"{label} source_id"),
        target_genes=_text_sequence(
            raw["target_genes"],
            f"{label} target_genes",
            allow_empty=True,
            max_items=MAX_CASE_TARGETS_PER_ELEMENT,
        ),
        state_ids=_text_sequence(
            raw["state_ids"],
            f"{label} state_ids",
            allow_empty=True,
            max_items=MAX_CASE_TARGETS_PER_ELEMENT,
        ),
        features=_FrozenJsonObject(features),
        annotations=_json_mapping(raw["annotations"], f"{label} annotations"),
    )


def _case_runtime_work_items(
    variants: Sequence[VariantIdentity],
    elements: Sequence[CandidateElement],
) -> int:
    """Conservatively bound pair scans and downstream target expansion."""

    per_variant = sum(
        1 + max(1, len(element.target_genes)) + max(1, len(element.state_ids))
        for element in elements
    )
    # Even a live-reference case without declared candidates produces one
    # abstention pass per variant.
    return len(variants) * max(1, per_variant)


def _candidate_sort_key(element: CandidateElement) -> tuple[str, str, str, int, int]:
    return (
        element.element_id,
        element.source_id,
        element.chromosome,
        element.start,
        element.end,
    )


def _candidate_output_address(
    *,
    batch_address: str,
    context: ReferenceContext,
    source_metadata: Mapping[str, Any],
    target_gene_keys: Sequence[str],
    elements: Sequence[CandidateElement],
    canonical_order: bool = True,
) -> str:
    ordered_elements = (
        sorted(elements, key=_candidate_sort_key) if canonical_order else elements
    )
    return content_hash(
        {
            "version": WORKFLOW_VERSION,
            "batch_address": batch_address,
            "context": context.to_dict(),
            "source_metadata": jsonable(dict(source_metadata)),
            "target_gene_keys": list(target_gene_keys),
            "candidate_elements": [item.to_dict() for item in ordered_elements],
        }
    )


def _legacy_candidate_order(
    elements: Sequence[CandidateElement],
) -> tuple[CandidateElement, ...]:
    """Recover the parser order used by legacy v1 candidate addresses."""

    indexed: list[tuple[int, CandidateElement]] = []
    for element in elements:
        source_line = element.annotations.get("track_line")
        if type(source_line) is not int or source_line < 1:
            raise ValidationError(
                "legacy candidate provenance lacks canonical parser line evidence"
            )
        indexed.append((source_line, element))
    if len({line for line, _ in indexed}) != len(indexed):
        raise ValidationError("legacy candidate provenance has duplicate parser line evidence")
    return tuple(item for _, item in sorted(indexed, key=lambda pair: pair[0]))


def _validate_case_runtime_work(
    variants: Sequence[VariantIdentity],
    elements: Sequence[CandidateElement],
    *,
    label: str,
) -> int:
    if any(
        len(element.target_genes) > MAX_CASE_TARGETS_PER_ELEMENT
        or len(element.state_ids) > MAX_CASE_TARGETS_PER_ELEMENT
        for element in elements
    ):
        raise ValidationError(
            f"{label} exceeds the maximum of {MAX_CASE_TARGETS_PER_ELEMENT} "
            "target genes or state IDs per candidate element"
        )
    work_items = _case_runtime_work_items(variants, elements)
    if work_items > MAX_CASE_RUNTIME_WORK_ITEMS:
        raise ValidationError(
            f"{label} requires {work_items} conservative runtime work items; "
            f"maximum is {MAX_CASE_RUNTIME_WORK_ITEMS}"
        )
    return work_items


def _verify_address(raw: Mapping[str, Any], actual: str, label: str) -> None:
    supplied = raw.get("content_address")
    if not isinstance(supplied, str) or supplied != actual:
        raise ValidationError(f"{label} content_address does not match its canonical payload")


def _strict_run_record(value: Mapping[str, Any]) -> _FrozenJsonObject:
    raw = _strict_mapping(
        value,
        allowed=_RUN_RECORD_FIELDS,
        required=_RUN_RECORD_FIELDS,
        label="run record",
    )
    event_history = _text_sequence(
        raw["event_history"],
        "run record event_history",
        allow_empty=False,
        max_items=MAX_RUN_HISTORY_ENTRIES,
    )
    dossier_history = _text_sequence(
        raw["dossier_history"],
        "run record dossier_history",
        allow_empty=False,
        max_items=MAX_RUN_HISTORY_ENTRIES,
    )
    event_history = tuple(
        _sha256_address(item, "run record event_history item") for item in event_history
    )
    dossier_history = tuple(
        _sha256_address(item, "run record dossier_history item") for item in dossier_history
    )
    event_address = _sha256_address(raw["event_address"], "run record event_address")
    dossier_address = _sha256_address(raw["dossier_address"], "run record dossier_address")
    if event_address not in event_history:
        raise ValidationError("run record event_address is absent from event_history")
    if dossier_address not in dossier_history:
        raise ValidationError("run record dossier_address is absent from dossier_history")
    return _FrozenJsonObject(
        {
            "run_id": _run_identifier(raw["run_id"], "run record run_id"),
            "input_address": _sha256_address(
                raw["input_address"],
                "run record input_address",
            ),
            "event_address": event_address,
            "event_history": _FrozenJsonArray(event_history),
            "dossier_address": dossier_address,
            "dossier_history": _FrozenJsonArray(dossier_history),
        }
    )


def _dossier_address(dossier: Dossier) -> str:
    payload = dossier.to_dict()
    supplied = payload.pop("content_address", None)
    actual = content_hash(payload)
    if not isinstance(supplied, str) or supplied != actual:
        raise ValidationError("dossier content_address does not match its hydrated payload")
    return actual


def _strict_dossier(value: Mapping[str, Any]) -> Dossier:
    raw = _strict_mapping(
        value,
        allowed=_DOSSIER_FIELDS,
        required=_DOSSIER_FIELDS,
        label="run result dossier",
    )
    # Canonicalize before hashing or model hydration so recursive/deep payloads
    # always fail through the workflow ValidationError boundary.
    raw = _json_mapping(raw, "run result dossier")
    for field_name in (
        "dossier_id",
        "case_id",
        "created_at",
        "policy_version",
        "status",
    ):
        _required_text(raw[field_name], f"run result dossier {field_name}")
    run_id = _run_identifier(raw["run_id"], "run result dossier run_id")
    _sha256_address(raw["input_address"], "run result dossier input_address")
    _sha256_address(raw["event_head"], "run result dossier event_head")
    _sha256_address(raw["content_address"], "run result dossier content_address")
    if raw["dossier_id"] != f"dos-{run_id}":
        raise ValidationError("run result dossier dossier_id does not match run_id")
    if type(raw["research_use_only"]) is not bool:
        raise ValidationError("run result dossier research_use_only must be a boolean")
    for field_name in (
        "hypotheses",
        "evidence",
        "experiments",
        "warnings",
        "source_receipts",
        "source_bundle_addresses",
    ):
        _sequence(raw[field_name], f"run result dossier {field_name}")
    if raw["review"] is not None and not isinstance(raw["review"], Mapping):
        raise ValidationError("run result dossier review must be an object or null")
    for item in raw["source_bundle_addresses"]:
        _sha256_address(item, "run result dossier source_bundle_addresses item")

    supplied = raw["content_address"]
    raw_payload = {key: item for key, item in raw.items() if key != "content_address"}
    if supplied != content_hash(raw_payload):
        raise ValidationError("dossier content_address does not match its canonical payload")
    try:
        dossier = Dossier.from_dict(raw)
    except ValidationError:
        raise
    except (AttributeError, KeyError, OverflowError, TypeError, ValueError, RecursionError) as exc:
        raise ValidationError("run result dossier failed typed hydration") from exc
    if _dossier_address(dossier) != supplied:
        raise ValidationError("dossier payload changes under typed hydration")

    for index, evidence in enumerate(dossier.evidence):
        object.__setattr__(
            evidence,
            "payload",
            _json_mapping(evidence.payload, f"dossier evidence {index} payload"),
        )
    object.__setattr__(
        dossier,
        "source_receipts",
        tuple(
            _json_mapping(item, f"dossier source receipt {index}")
            for index, item in enumerate(dossier.source_receipts)
        ),
    )
    _dossier_address(dossier)
    return dossier


def _strict_manifest(value: Mapping[str, Any]) -> CaseManifest:
    raw = _strict_mapping(
        value,
        allowed=_MANIFEST_FIELDS,
        required=_MANIFEST_FIELDS,
        label="prepared manifest",
    )
    context_raw = raw["context"]
    if not isinstance(context_raw, Mapping):
        raise ValidationError("prepared manifest context must be an object")
    _strict_mapping(
        context_raw,
        allowed=_CONTEXT_FIELDS,
        required=_CONTEXT_FIELDS,
        label="prepared manifest context",
    )
    manifest_context = _context(context_raw, "prepared manifest context")
    raw["case_id"] = _required_text(raw["case_id"], "prepared manifest case_id")
    raw["subject_id"] = _required_text(
        raw["subject_id"],
        "prepared manifest subject_id",
    )
    raw["requested_by"] = _required_text(
        raw["requested_by"],
        "prepared manifest requested_by",
    )
    manifest_metadata = _json_mapping(raw["metadata"], "prepared manifest metadata")
    input_versions = _text_mapping(
        raw["input_versions"],
        "prepared manifest input_versions",
    )
    variant_values = _sequence(raw["variants"], "prepared manifest variants")
    if len(variant_values) > MAX_VARIANT_INTAKE_RECORDS:
        raise ValidationError(
            "prepared manifest variants exceeds the maximum of "
            f"{MAX_VARIANT_INTAKE_RECORDS} records"
        )
    variants = tuple(
        _variant_identity(item, f"prepared manifest variant {index}")
        for index, item in enumerate(variant_values)
    )
    element_values = _sequence(
        raw["candidate_elements"],
        "prepared manifest candidate_elements",
    )
    if len(element_values) > MAX_CASE_CANDIDATE_ELEMENTS:
        raise ValidationError(
            "prepared manifest candidate_elements exceeds the maximum of "
            f"{MAX_CASE_CANDIDATE_ELEMENTS} records"
        )
    elements = tuple(
        _candidate_element(item, f"prepared manifest candidate element {index}")
        for index, item in enumerate(element_values)
    )
    _validate_case_runtime_work(variants, elements, label="prepared manifest")
    return CaseManifest(
        case_id=raw["case_id"],
        subject_id=raw["subject_id"],
        context=manifest_context,
        variants=variants,
        candidate_elements=elements,
        metadata=manifest_metadata,
        input_versions=input_versions,
        requested_by=raw["requested_by"],
    )


def _normalize_rna_consequences(
    values: Iterable[RNAConsequenceEvidence | Mapping[str, Any]],
) -> tuple[RNAConsequenceEvidence, ...]:
    if isinstance(values, (str, bytes, bytearray, Mapping)):
        raise ValidationError("rna_consequences must be an iterable of evidence objects")
    try:
        items = tuple(islice(iter(values), MAX_CASE_RNA_CONSEQUENCES + 1))
    except TypeError as exc:
        raise ValidationError("rna_consequences must be iterable") from exc
    if len(items) > MAX_CASE_RNA_CONSEQUENCES:
        raise ValidationError(
            f"rna_consequences exceeds the maximum of {MAX_CASE_RNA_CONSEQUENCES} evidence objects"
        )

    normalized: list[RNAConsequenceEvidence] = []
    for index, item in enumerate(items):
        if isinstance(item, RNAConsequenceEvidence):
            raw = item.to_dict()
        elif not isinstance(item, Mapping):
            raise ValidationError(
                f"rna_consequences item {index} must be RNAConsequenceEvidence or an object"
            )
        else:
            raw = _strict_mapping(
                item,
                allowed=_RNA_CONSEQUENCE_FIELDS,
                required=_RNA_CONSEQUENCE_REQUIRED_FIELDS,
                label=f"rna_consequences item {index}",
            )
        if raw["schema_version"] != EXPRESSION_EVIDENCE_SCHEMA_VERSION:
            raise ValidationError(
                f"rna_consequences item {index} has an unsupported schema_version"
            )
        if "content_address" in raw and not isinstance(raw["content_address"], str):
            raise ValidationError(f"rna_consequences item {index} content_address must be a string")
        raw["reason_codes"] = _text_sequence(
            raw["reason_codes"],
            f"rna_consequences item {index} reason_codes",
            allow_empty=True,
        )
        normalized.append(RNAConsequenceEvidence.from_mapping(raw))
    addresses = [item.content_address for item in normalized]
    if len(set(addresses)) != len(addresses):
        raise ValidationError("rna_consequences contains duplicate evidence objects")
    return tuple(sorted(normalized, key=lambda item: item.content_address))


def _bounded_regulatory_tracks(
    values: Iterable[RegulatoryTrackSource | Mapping[str, Any]],
    label: str,
) -> tuple[RegulatoryTrackSource | Mapping[str, Any], ...]:
    if isinstance(values, (str, bytes, bytearray, Mapping)):
        raise ValidationError(f"{label} must be an iterable of track objects")
    try:
        items = tuple(islice(iter(values), MAX_CASE_REGULATORY_TRACKS + 1))
    except TypeError as exc:
        raise ValidationError(f"{label} must be iterable") from exc
    if len(items) > MAX_CASE_REGULATORY_TRACKS:
        raise ValidationError(f"{label} exceeds the maximum of {MAX_CASE_REGULATORY_TRACKS} tracks")
    return items


def _runtime_rna_input_address(event_record: object) -> str | None:
    if not isinstance(event_record, Mapping):
        return None
    events = event_record.get("events")
    if not isinstance(events, Sequence) or isinstance(events, (str, bytes, bytearray)):
        return None
    for event in events:
        if not isinstance(event, Mapping) or event.get("event_type") != "case_received":
            continue
        payload = event.get("payload")
        if not isinstance(payload, Mapping):
            return None
        address = payload.get("rna_input_address")
        return address if isinstance(address, str) and address else None
    return None


def _decode_payload(payload: str | bytes, label: str) -> str:
    if isinstance(payload, str):
        return payload
    try:
        return payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValidationError(f"{label} bytes must contain UTF-8 text") from exc


def _payload_address(payload: str | bytes) -> str:
    if isinstance(payload, str):
        return content_hash(payload)
    try:
        return content_hash(payload.decode("utf-8-sig"))
    except UnicodeDecodeError:
        return hash_bytes(payload)


def _encoded_payload(payload: str | bytes) -> tuple[str, str]:
    if isinstance(payload, str):
        return payload, "text"
    return base64.b64encode(payload).decode("ascii"), "base64"


def _decoded_mapping_payload(raw: Mapping[str, Any], label: str) -> str | bytes:
    candidates = [name for name in ("payload", "data", "text") if name in raw]
    if len(candidates) != 1:
        raise ValidationError(f"{label} must contain exactly one of payload, data, or text")
    encoding_candidates = [name for name in ("payload_encoding", "data_encoding") if name in raw]
    if len(encoding_candidates) > 1:
        raise ValidationError(f"{label} must contain at most one payload encoding declaration")
    value = raw[candidates[0]]
    if not isinstance(value, str):
        raise ValidationError(f"{label} payload must be a string")
    encoding = raw.get("payload_encoding", raw.get("data_encoding", "text"))
    if not isinstance(encoding, str):
        raise ValidationError(f"{label} payload encoding must be text or base64")
    if encoding == "text":
        return value
    if encoding != "base64":
        raise ValidationError(f"{label} payload encoding must be text or base64")
    try:
        encoded = value.encode("ascii")
        decoded = base64.b64decode(encoded, validate=True)
    except (ValueError, UnicodeEncodeError) as exc:
        raise ValidationError(f"{label} payload is not valid base64") from exc
    if base64.b64encode(decoded) != encoded:
        raise ValidationError(f"{label} payload is not canonical base64")
    return decoded


@dataclass(frozen=True, slots=True)
class VariantSource:
    """A declared, in-memory variant source; no path-valued input exists."""

    source_id: str
    input_format: IntakeFormat | str
    genome_build: str
    payload: str | bytes
    sample_id: str | None = None
    include_no_call: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_id", _required_text(self.source_id, "source_id"))
        object.__setattr__(self, "genome_build", _required_text(self.genome_build, "genome_build"))
        selected_format = _required_text(self.input_format, "input_format")
        try:
            selected = IntakeFormat(selected_format)
        except ValueError as exc:
            raise ValidationError(f"unsupported intake format: {self.input_format}") from exc
        object.__setattr__(self, "input_format", selected)
        if not isinstance(self.payload, (str, bytes)):
            raise ValidationError("variant payload must be text or bytes")
        if self.sample_id is not None:
            object.__setattr__(self, "sample_id", _required_text(self.sample_id, "sample_id"))
        if type(self.include_no_call) is not bool:
            raise ValidationError("include_no_call must be a boolean")
        object.__setattr__(self, "metadata", _json_mapping(self.metadata, "variant metadata"))

    @property
    def input_address(self) -> str:
        return _payload_address(self.payload)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> VariantSource:
        raw = _strict_mapping(
            value,
            allowed={
                "source_id",
                "input_format",
                "format",
                "genome_build",
                "payload",
                "data",
                "text",
                "payload_encoding",
                "data_encoding",
                "sample_id",
                "include_no_call",
                "metadata",
            },
            required={"source_id", "genome_build"},
            label="variant source",
        )
        selected_format = raw.get("input_format", raw.get("format"))
        if selected_format is None or ("input_format" in raw and "format" in raw):
            raise ValidationError("variant source requires exactly one format declaration")
        include_no_call = raw.get("include_no_call", False)
        if type(include_no_call) is not bool:
            raise ValidationError("include_no_call must be a boolean")
        return cls(
            source_id=raw["source_id"],
            input_format=selected_format,
            genome_build=raw["genome_build"],
            payload=_decoded_mapping_payload(raw, "variant source"),
            sample_id=raw.get("sample_id"),
            include_no_call=include_no_call,
            metadata=_json_mapping(raw.get("metadata", {}), "variant metadata"),
        )

    def to_dict(self) -> dict[str, Any]:
        payload, encoding = _encoded_payload(self.payload)
        return {
            "source_id": self.source_id,
            "input_format": str(self.input_format),
            "genome_build": self.genome_build,
            "payload": payload,
            "payload_encoding": encoding,
            "sample_id": self.sample_id,
            "include_no_call": self.include_no_call,
            "metadata": jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True, slots=True)
class RegulatoryTrackSource:
    """A context-qualified, in-memory regulatory interval source."""

    source_id: str
    input_format: RegulatoryTrackFormat | str
    genome_build: str
    context: ReferenceContext | Mapping[str, Any]
    payload: str | bytes
    metadata: Mapping[str, Any] = field(default_factory=dict)
    target_gene_keys: tuple[str, ...] = ("gene", "gene_id", "gene_name", "target_gene")

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_id", _required_text(self.source_id, "source_id"))
        object.__setattr__(self, "genome_build", _required_text(self.genome_build, "genome_build"))
        selected_format = _required_text(self.input_format, "input_format")
        try:
            selected = RegulatoryTrackFormat(selected_format)
        except ValueError as exc:
            raise ValidationError(
                f"unsupported regulatory track format: {self.input_format}"
            ) from exc
        object.__setattr__(self, "input_format", selected)
        object.__setattr__(self, "context", _context(self.context, "track context"))
        if not isinstance(self.payload, (str, bytes)):
            raise ValidationError("regulatory track payload must be text or bytes")
        object.__setattr__(self, "metadata", _json_mapping(self.metadata, "track metadata"))
        keys = _text_sequence(
            self.target_gene_keys,
            "target_gene_keys",
            allow_empty=False,
            max_items=MAX_CASE_TARGET_GENE_KEYS,
            max_item_length=MAX_CASE_TARGET_GENE_KEY_LENGTH,
        )
        object.__setattr__(self, "target_gene_keys", keys)

    @property
    def input_address(self) -> str:
        return _payload_address(self.payload)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegulatoryTrackSource:
        raw = _strict_mapping(
            value,
            allowed={
                "source_id",
                "input_format",
                "format",
                "genome_build",
                "context",
                "payload",
                "data",
                "text",
                "payload_encoding",
                "data_encoding",
                "metadata",
                "target_gene_keys",
            },
            required={"source_id", "genome_build", "context"},
            label="regulatory track source",
        )
        selected_format = raw.get("input_format", raw.get("format"))
        if selected_format is None or ("input_format" in raw and "format" in raw):
            raise ValidationError("regulatory track source requires exactly one format declaration")
        context_raw = raw["context"]
        if not isinstance(context_raw, (ReferenceContext, Mapping)):
            raise ValidationError("track context must be an object")
        keys_raw = raw.get("target_gene_keys", ("gene", "gene_id", "gene_name", "target_gene"))
        keys = _text_sequence(
            keys_raw,
            "target_gene_keys",
            allow_empty=False,
            max_items=MAX_CASE_TARGET_GENE_KEYS,
            max_item_length=MAX_CASE_TARGET_GENE_KEY_LENGTH,
        )
        return cls(
            source_id=raw["source_id"],
            input_format=selected_format,
            genome_build=raw["genome_build"],
            context=context_raw,
            payload=_decoded_mapping_payload(raw, "regulatory track source"),
            metadata=_json_mapping(raw.get("metadata", {}), "track metadata"),
            target_gene_keys=keys,
        )

    def to_dict(self) -> dict[str, Any]:
        payload, encoding = _encoded_payload(self.payload)
        assert isinstance(self.context, ReferenceContext)
        return {
            "source_id": self.source_id,
            "input_format": str(self.input_format),
            "genome_build": self.genome_build,
            "context": self.context.to_dict(),
            "payload": payload,
            "payload_encoding": encoding,
            "metadata": jsonable(dict(self.metadata)),
            "target_gene_keys": list(self.target_gene_keys),
        }


# Explicit aliases make the transport role discoverable without duplicating contracts.
VariantSourceInput = VariantSource
RegulatoryTrackSourceInput = RegulatoryTrackSource


@dataclass(frozen=True, slots=True)
class WorkflowIssue:
    """An addressed, stage-qualified problem or warning."""

    code: str
    severity: WorkflowSeverity | str
    stage: WorkflowStage | str
    message: str
    source_id: str | None = None
    line_number: int | None = None
    raw_hash: str | None = None
    remediation: str = "Inspect the addressed stage evidence and correct the declared input."

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", _required_text(self.code, "issue code"))
        object.__setattr__(self, "message", _required_text(self.message, "issue message"))
        try:
            severity = WorkflowSeverity(_required_text(self.severity, "issue severity"))
        except ValueError as exc:
            raise ValidationError(f"unsupported issue severity: {self.severity}") from exc
        try:
            stage = WorkflowStage(_required_text(self.stage, "issue stage"))
        except ValueError as exc:
            raise ValidationError(f"unsupported issue stage: {self.stage}") from exc
        object.__setattr__(self, "severity", severity)
        object.__setattr__(self, "stage", stage)
        if self.source_id is not None:
            object.__setattr__(self, "source_id", _required_text(self.source_id, "source_id"))
        if self.line_number is not None:
            if type(self.line_number) is not int or self.line_number < 1:
                raise ValidationError("issue line_number must be a positive integer")
        if self.raw_hash is not None:
            object.__setattr__(self, "raw_hash", _required_text(self.raw_hash, "raw_hash"))
        object.__setattr__(
            self,
            "remediation",
            _required_text(self.remediation, "issue remediation"),
        )

    def _body(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": str(self.severity),
            "stage": str(self.stage),
            "message": self.message,
            "source_id": self.source_id,
            "line_number": self.line_number,
            "raw_hash": self.raw_hash,
            "remediation": self.remediation,
        }

    @property
    def content_address(self) -> str:
        return content_hash(self._body())

    def to_dict(self) -> dict[str, Any]:
        return self._body() | {"content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> WorkflowIssue:
        raw = _strict_mapping(
            value,
            allowed={
                "code",
                "severity",
                "stage",
                "message",
                "source_id",
                "line_number",
                "raw_hash",
                "remediation",
                "content_address",
            },
            required={
                "code",
                "severity",
                "stage",
                "message",
                "source_id",
                "line_number",
                "raw_hash",
                "remediation",
                "content_address",
            },
            label="workflow issue",
        )
        line = raw.get("line_number")
        issue = cls(
            code=raw["code"],
            severity=raw["severity"],
            stage=raw["stage"],
            message=raw["message"],
            source_id=raw["source_id"],
            line_number=line,
            raw_hash=raw["raw_hash"],
            remediation=raw["remediation"],
        )
        _verify_address(raw, issue.content_address, "workflow issue")
        return issue


@dataclass(frozen=True, slots=True)
class StageReceipt:
    """Addressed stage evidence with an observational (non-identity) timestamp."""

    stage: WorkflowStage | str
    state: WorkflowState | str
    source_id: str
    input_address: str
    output_address: str | None
    observed_at: str
    record_count: int = 0
    accepted_count: int = 0
    rejected_count: int = 0
    warning_count: int = 0
    error_count: int = 0
    issue_addresses: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        try:
            stage = WorkflowStage(_required_text(self.stage, "receipt stage"))
        except ValueError as exc:
            raise ValidationError(f"unsupported receipt stage: {self.stage}") from exc
        try:
            state = WorkflowState(_required_text(self.state, "receipt state"))
        except ValueError as exc:
            raise ValidationError(f"unsupported receipt state: {self.state}") from exc
        object.__setattr__(self, "stage", stage)
        object.__setattr__(self, "state", state)
        object.__setattr__(self, "source_id", _required_text(self.source_id, "receipt source_id"))
        object.__setattr__(
            self, "input_address", _sha256_address(self.input_address, "input_address")
        )
        object.__setattr__(self, "observed_at", _required_text(self.observed_at, "observed_at"))
        if self.output_address is not None:
            object.__setattr__(
                self, "output_address", _sha256_address(self.output_address, "output_address")
            )
        for name in (
            "record_count",
            "accepted_count",
            "rejected_count",
            "warning_count",
            "error_count",
        ):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise ValidationError(f"receipt {name} must be a non-negative integer")
        issue_addresses = _text_sequence(
            self.issue_addresses,
            "receipt issue_addresses",
            allow_empty=True,
        )
        object.__setattr__(
            self,
            "issue_addresses",
            tuple(
                _sha256_address(item, "receipt issue_addresses item")
                for item in issue_addresses
            ),
        )
        object.__setattr__(self, "metadata", _json_mapping(self.metadata, "receipt metadata"))

    def _identity_body(self) -> dict[str, Any]:
        # observed_at is intentionally absent: it is evidence, not scientific identity.
        return {
            "stage": str(self.stage),
            "state": str(self.state),
            "source_id": self.source_id,
            "input_address": self.input_address,
            "output_address": self.output_address,
            "record_count": self.record_count,
            "accepted_count": self.accepted_count,
            "rejected_count": self.rejected_count,
            "warning_count": self.warning_count,
            "error_count": self.error_count,
            "issue_addresses": list(self.issue_addresses),
            "metadata": jsonable(dict(self.metadata)),
        }

    @property
    def content_address(self) -> str:
        return content_hash(self._identity_body())

    def to_dict(self) -> dict[str, Any]:
        return self._identity_body() | {
            "observed_at": self.observed_at,
            "content_address": self.content_address,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> StageReceipt:
        raw = _strict_mapping(
            value,
            allowed={
                "stage",
                "state",
                "source_id",
                "input_address",
                "output_address",
                "observed_at",
                "record_count",
                "accepted_count",
                "rejected_count",
                "warning_count",
                "error_count",
                "issue_addresses",
                "metadata",
                "content_address",
            },
            required={
                "stage",
                "state",
                "source_id",
                "input_address",
                "output_address",
                "observed_at",
                "record_count",
                "accepted_count",
                "rejected_count",
                "warning_count",
                "error_count",
                "issue_addresses",
                "metadata",
                "content_address",
            },
            label="stage receipt",
        )
        receipt = cls(
            stage=raw["stage"],
            state=raw["state"],
            source_id=raw["source_id"],
            input_address=raw["input_address"],
            output_address=raw["output_address"],
            observed_at=raw["observed_at"],
            record_count=raw["record_count"],
            accepted_count=raw["accepted_count"],
            rejected_count=raw["rejected_count"],
            warning_count=raw["warning_count"],
            error_count=raw["error_count"],
            issue_addresses=raw["issue_addresses"],
            metadata=_json_mapping(raw["metadata"], "receipt metadata"),
        )
        _verify_address(raw, receipt.content_address, "stage receipt")
        return receipt


@dataclass(frozen=True, slots=True)
class PreparedCase:
    """A deterministic manifest decision plus complete preparation evidence."""

    state: WorkflowState | str
    manifest: CaseManifest | None
    run_id: str | None
    live_reference: bool
    stage_receipts: tuple[StageReceipt, ...]
    issues: tuple[WorkflowIssue, ...] = ()

    def __post_init__(self) -> None:
        try:
            state = WorkflowState(_required_text(self.state, "prepared state"))
        except ValueError as exc:
            raise ValidationError(f"unsupported prepared state: {self.state}") from exc
        object.__setattr__(self, "state", state)
        if type(self.live_reference) is not bool:
            raise ValidationError("live_reference must be a boolean")
        if self.manifest is not None:
            if not isinstance(self.manifest, CaseManifest):
                raise ValidationError("prepared manifest must be a CaseManifest or null")
            object.__setattr__(self, "manifest", _strict_manifest(self.manifest.to_dict()))
        if self.run_id is not None:
            object.__setattr__(
                self,
                "run_id",
                _run_identifier(self.run_id, "prepared run_id"),
            )
        receipts = tuple(self.stage_receipts)
        if any(not isinstance(item, StageReceipt) for item in receipts):
            raise ValidationError("prepared stage_receipts must contain StageReceipt objects")
        issues = tuple(self.issues)
        if any(not isinstance(item, WorkflowIssue) for item in issues):
            raise ValidationError("prepared issues must contain WorkflowIssue objects")
        object.__setattr__(self, "stage_receipts", receipts)
        object.__setattr__(self, "issues", issues)
        if self.accepted:
            if self.manifest is None or not self.run_id:
                raise ValidationError("accepted preparation requires a manifest and run_id")
            if any(issue.severity == WorkflowSeverity.ERROR for issue in self.issues):
                raise ValidationError("accepted preparation cannot contain error issues")
            expected = _run_id(self.manifest)
            if self.run_id != expected:
                raise ValidationError("prepared run_id does not match the manifest identity")
            self._validate_accepted_bundle()
        elif self.manifest is not None or self.run_id is not None:
            raise ValidationError("blocked preparation must not expose an executable manifest")

    def _validate_accepted_bundle(self) -> None:
        """Replay accepted hard gates and close every preparation evidence link."""

        assert self.manifest is not None
        manifest = self.manifest
        variants = manifest.variants
        elements = manifest.candidate_elements
        if not variants:
            raise ValidationError("accepted preparation requires at least one variant")
        if not elements and not self.live_reference:
            raise ValidationError(
                "accepted preparation requires candidate elements unless live_reference is enabled"
            )
        if len({item.variant_id for item in variants}) != len(variants):
            raise ValidationError("accepted preparation contains duplicate variant IDs")
        if len({item.element_id for item in elements}) != len(elements):
            raise ValidationError("accepted preparation contains duplicate candidate element IDs")
        if any(
            not _same_build(item.genome_build, manifest.context.genome_build)
            for item in variants
        ):
            raise ValidationError(
                "accepted preparation variant genome build does not match manifest"
            )
        if any(
            not _same_build(item.context.genome_build, manifest.context.genome_build)
            for item in elements
        ):
            raise ValidationError(
                "accepted preparation candidate genome build does not match manifest"
            )
        expected_variants = tuple(
            sorted(variants, key=lambda item: (item.canonical_key, item.variant_id))
        )
        expected_elements = tuple(
            sorted(
                elements,
                key=lambda item: (
                    item.element_id,
                    item.source_id,
                    item.chromosome,
                    item.start,
                    item.end,
                ),
            )
        )
        if variants != expected_variants or elements != expected_elements:
            raise ValidationError("accepted preparation manifest collections are not canonical")
        _validate_case_runtime_work(variants, elements, label="accepted preparation")

        provenance_value = manifest.metadata.get("case_workflow_provenance")
        if not isinstance(provenance_value, Mapping):
            raise ValidationError("accepted preparation requires case_workflow_provenance")
        provenance = _strict_mapping(
            provenance_value,
            allowed={
                "version",
                "identity_policy",
                "variant_source",
                "regulatory_tracks",
                "canonical_order",
                "live_reference",
            },
            required={
                "version",
                "identity_policy",
                "variant_source",
                "regulatory_tracks",
                "canonical_order",
                "live_reference",
            },
            label="accepted preparation provenance",
        )
        if provenance["version"] != WORKFLOW_VERSION:
            raise ValidationError("accepted preparation provenance version is unsupported")
        if type(provenance["live_reference"]) is not bool:
            raise ValidationError("accepted preparation provenance live_reference must be boolean")
        if provenance["live_reference"] != self.live_reference:
            raise ValidationError("accepted preparation live_reference provenance does not match")
        if provenance["identity_policy"] != "observational timestamps excluded":
            raise ValidationError("accepted preparation identity policy is unsupported")
        if provenance["canonical_order"] != {
            "tracks": "source_id, format, build, context, payload address",
            "variants": "canonical_key, variant_id",
            "candidate_elements": "element_id, source_id, chromosome, start, end",
        }:
            raise ValidationError("accepted preparation canonical order provenance is invalid")

        variant_value = provenance["variant_source"]
        if not isinstance(variant_value, Mapping):
            raise ValidationError("accepted preparation variant provenance must be an object")
        variant_source = _strict_mapping(
            variant_value,
            allowed={
                "source_id",
                "input_format",
                "genome_build",
                "input_address",
                "batch_address",
                "intake_receipt",
                "source_metadata",
            },
            required={
                "source_id",
                "input_format",
                "genome_build",
                "input_address",
                "batch_address",
                "intake_receipt",
                "source_metadata",
            },
            label="accepted preparation variant provenance",
        )
        variant_source_id = _required_text(
            variant_source["source_id"], "accepted preparation variant source_id"
        )
        variant_input = _sha256_address(
            variant_source["input_address"], "accepted preparation variant input_address"
        )
        variant_batch = _sha256_address(
            variant_source["batch_address"], "accepted preparation variant batch_address"
        )
        variant_build = _required_text(
            variant_source["genome_build"], "accepted preparation variant genome_build"
        )
        if not _same_build(variant_build, manifest.context.genome_build):
            raise ValidationError("accepted preparation variant provenance build does not match")
        _required_text(variant_source["input_format"], "accepted preparation variant format")
        _json_mapping(variant_source["source_metadata"], "accepted preparation variant metadata")
        intake_value = variant_source["intake_receipt"]
        if not isinstance(intake_value, Mapping):
            raise ValidationError(
                "accepted preparation intake receipt provenance must be an object"
            )
        intake = _strict_mapping(
            intake_value,
            allowed={
                "source_id",
                "input_format",
                "input_hash",
                "header_hash",
                "record_count",
                "accepted_count",
                "rejected_count",
                "warning_count",
                "error_count",
                "content_address",
            },
            required={
                "source_id",
                "input_format",
                "input_hash",
                "header_hash",
                "record_count",
                "accepted_count",
                "rejected_count",
                "warning_count",
                "error_count",
                "content_address",
            },
            label="accepted preparation intake receipt provenance",
        )
        intake["source_id"] = _required_text(
            intake["source_id"], "accepted preparation intake receipt source_id"
        )
        intake["input_format"] = _required_text(
            intake["input_format"], "accepted preparation intake receipt input_format"
        )
        for address_name in ("input_hash", "header_hash", "content_address"):
            intake[address_name] = _sha256_address(
                intake[address_name],
                f"accepted preparation intake receipt {address_name}",
            )
        for count_name in (
            "record_count",
            "accepted_count",
            "rejected_count",
            "warning_count",
            "error_count",
        ):
            intake[count_name] = _integer(
                intake[count_name],
                f"accepted preparation intake receipt {count_name}",
            )
            if intake[count_name] < 0:
                raise ValidationError(
                    f"accepted preparation intake receipt {count_name} must be non-negative"
                )
        if (
            intake.get("source_id") != variant_source_id
            or intake.get("input_hash") != variant_input
        ):
            raise ValidationError("accepted preparation intake receipt provenance does not match")
        intake_address = str(intake["content_address"])
        intake_body = {key: item for key, item in intake.items() if key != "content_address"}
        if intake_address != content_hash(intake_body):
            raise ValidationError(
                "accepted preparation intake receipt content_address does not match"
            )

        track_values = _sequence(
            provenance["regulatory_tracks"],
            "accepted preparation regulatory_tracks provenance",
        )
        tracks: list[dict[str, Any]] = []
        for index, item in enumerate(track_values):
            if not isinstance(item, Mapping):
                raise ValidationError(
                    f"accepted preparation track provenance {index} must be an object"
                )
            track = _strict_mapping(
                item,
                allowed={
                    "source_id",
                    "input_format",
                    "genome_build",
                    "context",
                    "context_key",
                    "input_address",
                    "batch_address",
                    "candidate_address",
                    "feature_count",
                    "source_metadata",
                    "target_gene_keys",
                },
                required={
                    "source_id",
                    "input_format",
                    "genome_build",
                    "context_key",
                    "input_address",
                    "batch_address",
                    "candidate_address",
                    "feature_count",
                    "source_metadata",
                    "target_gene_keys",
                },
                label=f"accepted preparation track provenance {index}",
            )
            track["source_id"] = _required_text(
                track["source_id"], f"accepted preparation track provenance {index} source_id"
            )
            track["input_format"] = _required_text(
                track["input_format"], f"accepted preparation track provenance {index} format"
            )
            track["genome_build"] = _required_text(
                track["genome_build"],
                f"accepted preparation track provenance {index} genome_build",
            )
            track["context_key"] = _required_text(
                track["context_key"],
                f"accepted preparation track provenance {index} context_key",
            )
            if "context" in track:
                context_value = track["context"]
                if not isinstance(context_value, Mapping):
                    raise ValidationError(
                        f"accepted preparation track provenance {index} context must be an object"
                    )
                _strict_mapping(
                    context_value,
                    allowed=_CONTEXT_FIELDS,
                    required=_CONTEXT_FIELDS,
                    label=f"accepted preparation track provenance {index} context",
                )
                track["context"] = _context(
                    context_value,
                    f"accepted preparation track provenance {index} context",
                )
                if track["context"].key != track["context_key"]:
                    raise ValidationError(
                        "accepted preparation track context_key does not match its full context"
                    )
            for address_name in ("input_address", "batch_address", "candidate_address"):
                track[address_name] = _sha256_address(
                    track[address_name],
                    f"accepted preparation track provenance {index} {address_name}",
                )
            track["feature_count"] = _integer(
                track["feature_count"],
                f"accepted preparation track provenance {index} feature_count",
            )
            if track["feature_count"] < 0:
                raise ValidationError(
                    "accepted preparation track feature_count must be non-negative"
                )
            _json_mapping(
                track["source_metadata"],
                f"accepted preparation track provenance {index} metadata",
            )
            _text_sequence(
                track["target_gene_keys"],
                f"accepted preparation track provenance {index} target_gene_keys",
                allow_empty=False,
                max_items=MAX_CASE_TARGET_GENE_KEYS,
                max_item_length=MAX_CASE_TARGET_GENE_KEY_LENGTH,
            )
            if not _same_build(track["genome_build"], manifest.context.genome_build):
                raise ValidationError("accepted preparation track provenance build does not match")
            tracks.append(track)

        track_source_ids = [str(item["source_id"]) for item in tracks]
        canonical_tracks = sorted(
            tracks,
            key=lambda item: (
                str(item["source_id"]),
                str(item["input_format"]),
                str(item["genome_build"]),
                str(item["context_key"]),
                str(item["input_address"]),
                content_hash(item["source_metadata"]),
                content_hash(item["target_gene_keys"]),
            ),
        )
        if tracks != canonical_tracks:
            raise ValidationError("accepted preparation track provenance is not canonical")
        all_source_ids = [variant_source_id, *track_source_ids]
        if len(all_source_ids) != len(set(all_source_ids)):
            raise ValidationError("accepted preparation provenance source IDs must be unique")
        expected_inputs = {variant_source_id: variant_input}
        expected_inputs.update(
            {str(item["source_id"]): str(item["input_address"]) for item in tracks}
        )
        if dict(manifest.input_versions) != dict(sorted(expected_inputs.items())):
            raise ValidationError("accepted preparation input_versions do not match provenance")
        element_counts = Counter(item.source_id for item in elements)
        if set(element_counts) - set(track_source_ids):
            raise ValidationError("accepted preparation candidate source is absent from provenance")
        for track in tracks:
            source_id = str(track["source_id"])
            if element_counts[source_id] != track["feature_count"]:
                raise ValidationError(
                    "accepted preparation candidate counts do not match provenance"
                )
            source_elements = tuple(item for item in elements if item.source_id == source_id)
            track_context = track.get("context")
            legacy_context = track_context is None
            if legacy_context:
                if not source_elements:
                    # Legacy v1 omitted full context. With no candidates there is
                    # no surviving payload from which it can be recovered.
                    continue
                source_contexts = {item.context for item in source_elements}
                if len(source_contexts) != 1:
                    raise ValidationError(
                        "accepted preparation candidates from one source have different contexts"
                    )
                track_context = source_elements[0].context
                if track_context.key != track["context_key"]:
                    raise ValidationError(
                        "accepted preparation candidate context does not match provenance"
                    )
            else:
                assert isinstance(track_context, ReferenceContext)
                if any(item.context != track_context for item in source_elements):
                    raise ValidationError(
                        "accepted preparation candidate context does not match provenance"
                    )
            address_elements = (
                _legacy_candidate_order(source_elements)
                if legacy_context
                else source_elements
            )
            expected_candidate_address = _candidate_output_address(
                batch_address=str(track["batch_address"]),
                context=track_context,
                source_metadata=track["source_metadata"],
                target_gene_keys=track["target_gene_keys"],
                elements=address_elements,
                canonical_order=not legacy_context,
            )
            if track["candidate_address"] != expected_candidate_address:
                raise ValidationError(
                    "accepted preparation candidate address does not match its canonical payload"
                )

        receipts = self.stage_receipts
        if len(receipts) != len(tracks) + 2:
            raise ValidationError("accepted preparation receipt topology is incomplete")
        if [item.stage for item in receipts] != [
            WorkflowStage.VARIANT_INTAKE,
            *(WorkflowStage.REGULATORY_TRACK for _ in tracks),
            WorkflowStage.MANIFEST,
        ]:
            raise ValidationError("accepted preparation receipt stages are not canonical")
        if any(item.state != WorkflowState.ACCEPTED for item in receipts):
            raise ValidationError("accepted preparation receipts must all be accepted")
        issue_addresses = tuple(item.content_address for item in self.issues)
        known_issues = set(issue_addresses)
        if any(
            address not in known_issues
            for receipt in receipts
            for address in receipt.issue_addresses
        ):
            raise ValidationError("accepted preparation receipt references an unknown issue")

        variant_receipt = receipts[0]
        if (
            variant_receipt.source_id != variant_source_id
            or variant_receipt.input_address != variant_input
            or variant_receipt.output_address != variant_batch
            or variant_receipt.metadata.get("genome_build") != variant_build
            or variant_receipt.metadata.get("input_format") != variant_source["input_format"]
            or variant_receipt.metadata.get("intake_receipt_address") != intake_address
            or variant_receipt.metadata.get("header_address") != intake["header_hash"]
            or variant_receipt.record_count != intake["record_count"]
            or variant_receipt.accepted_count != intake["accepted_count"]
            or variant_receipt.rejected_count != intake["rejected_count"]
            or variant_receipt.warning_count != intake["warning_count"]
            or variant_receipt.error_count != intake["error_count"]
            or set(variant_receipt.metadata)
            != {
                "input_format",
                "genome_build",
                "header_address",
                "intake_receipt_address",
            }
        ):
            raise ValidationError("accepted preparation variant receipt does not match provenance")
        expected_variant_issues = tuple(
            item.content_address
            for item in self.issues
            if item.stage == WorkflowStage.VARIANT_INTAKE and item.source_id == variant_source_id
        )
        if variant_receipt.issue_addresses != expected_variant_issues:
            raise ValidationError("accepted preparation variant issue links do not close")
        if (
            variant_receipt.accepted_count != len(variants)
            or variant_receipt.warning_count
            != sum(
                item.severity == WorkflowSeverity.WARNING
                for item in self.issues
                if item.content_address in expected_variant_issues
            )
            or variant_receipt.error_count != 0
            or variant_receipt.rejected_count != 0
        ):
            raise ValidationError("accepted preparation variant receipt counters do not close")

        for index, (track, receipt) in enumerate(zip(tracks, receipts[1:-1], strict=True)):
            if (
                receipt.source_id != track["source_id"]
                or receipt.input_address != track["input_address"]
                or receipt.output_address != track["candidate_address"]
                or receipt.record_count != track["feature_count"]
                or receipt.accepted_count != track["feature_count"]
                or receipt.metadata.get("genome_build") != track["genome_build"]
                or receipt.metadata.get("context_key") != track["context_key"]
                or receipt.metadata.get("input_format") != track["input_format"]
                or receipt.metadata.get("track_batch_address") != track["batch_address"]
                or set(receipt.metadata)
                != {
                    "input_format",
                    "genome_build",
                    "context_key",
                    "header_address",
                    "track_batch_address",
                }
            ):
                raise ValidationError(
                    f"accepted preparation regulatory receipt {index} does not match provenance"
                )
            expected_track_issues = tuple(
                item.content_address
                for item in self.issues
                if item.stage == WorkflowStage.REGULATORY_TRACK
                and item.source_id == track["source_id"]
            )
            if receipt.issue_addresses != expected_track_issues:
                raise ValidationError("accepted preparation track issue links do not close")
            if (
                receipt.warning_count
                != sum(
                    item.severity == WorkflowSeverity.WARNING
                    for item in self.issues
                    if item.content_address in expected_track_issues
                )
                or receipt.error_count != 0
                or receipt.rejected_count != 0
            ):
                raise ValidationError("accepted preparation track receipt counters do not close")

        manifest_receipt = receipts[-1]
        user_metadata = dict(manifest.metadata)
        user_metadata.pop("case_workflow_provenance")
        expected_manifest_input = content_hash(
            {
                "version": WORKFLOW_VERSION,
                "case_id": manifest.case_id,
                "subject_id": manifest.subject_id,
                "requested_by": manifest.requested_by,
                "context": manifest.context.to_dict(),
                "variant_output_address": variant_receipt.output_address,
                "track_output_addresses": [item.output_address for item in receipts[1:-1]],
                "metadata": user_metadata,
                "live_reference": self.live_reference,
            }
        )
        if (
            manifest_receipt.source_id != manifest.case_id
            or manifest_receipt.input_address != expected_manifest_input
            or manifest_receipt.output_address != manifest.content_address
            or manifest_receipt.record_count != len(variants) + len(elements)
            or manifest_receipt.accepted_count != len(variants) + len(elements)
            or manifest_receipt.issue_addresses != issue_addresses
            or manifest_receipt.metadata.get("variant_count") != len(variants)
            or manifest_receipt.metadata.get("candidate_element_count") != len(elements)
            or manifest_receipt.metadata.get("track_count") != len(tracks)
            or manifest_receipt.metadata.get("live_reference") != self.live_reference
            or set(manifest_receipt.metadata)
            != {
                "variant_count",
                "candidate_element_count",
                "track_count",
                "live_reference",
            }
            or manifest_receipt.warning_count
            != sum(item.severity == WorkflowSeverity.WARNING for item in self.issues)
            or manifest_receipt.error_count != 0
            or manifest_receipt.rejected_count != 0
        ):
            raise ValidationError("accepted preparation manifest receipt does not close")

    def _validate_identity(self) -> None:
        if self.accepted:
            if self.manifest is None or self.run_id is None:
                raise ValidationError("accepted preparation lost its manifest identity")
            if self.run_id != _run_id(self.manifest):
                raise ValidationError("prepared run_id does not match the manifest identity")
            self._validate_accepted_bundle()
        elif self.manifest is not None or self.run_id is not None:
            raise ValidationError("blocked preparation exposes an executable manifest")

    @property
    def accepted(self) -> bool:
        return self.state == WorkflowState.ACCEPTED

    @property
    def blocked(self) -> bool:
        return not self.accepted

    @property
    def manifest_address(self) -> str | None:
        return None if self.manifest is None else self.manifest.content_address

    @property
    def provenance_addresses(self) -> tuple[str, ...]:
        addresses: list[str] = []
        for receipt in self.stage_receipts:
            addresses.extend((receipt.input_address, receipt.content_address))
            if receipt.output_address is not None:
                addresses.append(receipt.output_address)
        if self.manifest_address is not None:
            addresses.append(self.manifest_address)
        return tuple(dict.fromkeys(addresses))

    def _identity_body(self) -> dict[str, Any]:
        self._validate_identity()
        return {
            "version": WORKFLOW_VERSION,
            "state": str(self.state),
            "manifest_address": self.manifest_address,
            "run_id": self.run_id,
            "live_reference": self.live_reference,
            "stage_receipt_addresses": [item.content_address for item in self.stage_receipts],
            "issue_addresses": [item.content_address for item in self.issues],
        }

    @property
    def content_address(self) -> str:
        return content_hash(self._identity_body())

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": WORKFLOW_VERSION,
            "state": str(self.state),
            "accepted": self.accepted,
            "blocked": self.blocked,
            "manifest": None if self.manifest is None else self.manifest.to_dict(),
            "manifest_address": self.manifest_address,
            "run_id": self.run_id,
            "live_reference": self.live_reference,
            "stage_receipts": [item.to_dict() for item in self.stage_receipts],
            "issues": [item.to_dict() for item in self.issues],
            "content_address": self.content_address,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> PreparedCase:
        raw = _strict_mapping(
            value,
            allowed={
                "version",
                "state",
                "accepted",
                "blocked",
                "manifest",
                "manifest_address",
                "run_id",
                "live_reference",
                "stage_receipts",
                "issues",
                "content_address",
            },
            required={
                "version",
                "state",
                "accepted",
                "blocked",
                "manifest",
                "manifest_address",
                "run_id",
                "live_reference",
                "stage_receipts",
                "issues",
                "content_address",
            },
            label="prepared case",
        )
        if raw["version"] != WORKFLOW_VERSION:
            raise ValidationError(f"unsupported prepared case version: {raw['version']}")
        manifest_raw = raw["manifest"]
        if manifest_raw is not None and not isinstance(manifest_raw, Mapping):
            raise ValidationError("prepared manifest must be an object or null")
        manifest = None if manifest_raw is None else _strict_manifest(manifest_raw)
        prepared = cls(
            state=raw["state"],
            manifest=manifest,
            run_id=(
                None if raw["run_id"] is None else _required_text(raw["run_id"], "prepared run_id")
            ),
            live_reference=raw["live_reference"],
            stage_receipts=tuple(
                StageReceipt.from_mapping(item)
                for item in _sequence(raw["stage_receipts"], "stage_receipts")
            ),
            issues=tuple(
                WorkflowIssue.from_mapping(item) for item in _sequence(raw["issues"], "issues")
            ),
        )
        if type(raw["accepted"]) is not bool or type(raw["blocked"]) is not bool:
            raise ValidationError("prepared accepted and blocked fields must be booleans")
        if raw["accepted"] != prepared.accepted or raw["blocked"] != prepared.blocked:
            raise ValidationError("prepared state flags are inconsistent")
        if raw["manifest_address"] != prepared.manifest_address:
            raise ValidationError("prepared manifest_address does not match the manifest")
        _verify_address(raw, prepared.content_address, "prepared case")
        return prepared

    def public_summary(self) -> dict[str, Any]:
        """Return a payload/path-free summary suitable for user-facing surfaces."""

        counts = Counter(str(issue.severity) for issue in self.issues)
        return {
            "version": WORKFLOW_VERSION,
            "state": str(self.state),
            "accepted": self.accepted,
            "blocked": self.blocked,
            "case_id": None if self.manifest is None else self.manifest.case_id,
            "run_id": self.run_id,
            "manifest_address": self.manifest_address,
            "workflow_address": self.content_address,
            "variant_count": 0 if self.manifest is None else len(self.manifest.variants),
            "candidate_element_count": (
                0 if self.manifest is None else len(self.manifest.candidate_elements)
            ),
            "stage_receipt_addresses": [item.content_address for item in self.stage_receipts],
            "issue_counts": {
                "warning": counts[WorkflowSeverity.WARNING.value],
                "error": counts[WorkflowSeverity.ERROR.value],
            },
            "issue_codes": sorted({item.code for item in self.issues}),
            "live_reference": self.live_reference,
        }


@dataclass(frozen=True, slots=True)
class CaseRunResult:
    """Typed execution outcome carrying the persisted dossier and replay proof."""

    state: WorkflowState | str
    prepared: PreparedCase
    dossier: Dossier | None
    run_record: Mapping[str, Any] | None
    replay_report: ReplayReport | None
    stage_receipts: tuple[StageReceipt, ...]
    issues: tuple[WorkflowIssue, ...] = ()

    def __post_init__(self) -> None:
        try:
            state = WorkflowState(_required_text(self.state, "run state"))
        except ValueError as exc:
            raise ValidationError(f"unsupported run state: {self.state}") from exc
        object.__setattr__(self, "state", state)
        if not isinstance(self.prepared, PreparedCase):
            raise ValidationError("run prepared value must be a PreparedCase")
        if self.dossier is not None and not isinstance(self.dossier, Dossier):
            raise ValidationError("run dossier must be a Dossier or null")
        if self.dossier is not None:
            object.__setattr__(self, "dossier", _strict_dossier(self.dossier.to_dict()))
        if self.replay_report is not None:
            if not isinstance(self.replay_report, ReplayReport):
                raise ValidationError("run replay_report must be a ReplayReport or null")
            object.__setattr__(
                self,
                "replay_report",
                _replay_from_mapping(self.replay_report.to_dict()),
            )
        receipts = tuple(self.stage_receipts)
        if any(not isinstance(item, StageReceipt) for item in receipts):
            raise ValidationError("run stage_receipts must contain StageReceipt objects")
        issues = tuple(self.issues)
        if any(not isinstance(item, WorkflowIssue) for item in issues):
            raise ValidationError("run issues must contain WorkflowIssue objects")
        object.__setattr__(self, "stage_receipts", receipts)
        object.__setattr__(self, "issues", issues)
        if self.run_record is not None:
            object.__setattr__(self, "run_record", _strict_run_record(self.run_record))
        if self.accepted:
            if not self.prepared.accepted:
                raise ValidationError("an accepted run requires accepted preparation")
            if self.dossier is None or self.run_record is None or self.replay_report is None:
                raise ValidationError(
                    "an accepted run requires a dossier, run record, and replay report"
                )
            if any(issue.severity == WorkflowSeverity.ERROR for issue in self.issues):
                raise ValidationError("accepted run cannot contain error issues")
        self._validate_links()

    def _validate_links(self) -> None:
        if len(self.stage_receipts) != len(self.prepared.stage_receipts) + 1:
            raise ValidationError(
                "run receipts must extend the complete preparation receipt prefix"
            )
        if self.stage_receipts[:-1] != self.prepared.stage_receipts:
            raise ValidationError("run receipt prefix does not match preparation")
        if any(
            item.stage == WorkflowStage.CASE_RUNTIME for item in self.prepared.stage_receipts
        ):
            raise ValidationError("preparation receipt prefix cannot contain a runtime receipt")
        runtime_receipt = self.stage_receipts[-1]
        if runtime_receipt.stage != WorkflowStage.CASE_RUNTIME:
            raise ValidationError("run receipts must end with exactly one runtime receipt")
        if runtime_receipt.state != self.state:
            raise ValidationError("runtime receipt state does not match run state")

        prepared_issue_count = len(self.prepared.issues)
        if len(self.issues) < prepared_issue_count:
            raise ValidationError("run issues dropped preparation evidence")
        if self.issues[:prepared_issue_count] != self.prepared.issues:
            raise ValidationError("run issue prefix does not match preparation")
        if any(item.stage == WorkflowStage.CASE_RUNTIME for item in self.prepared.issues):
            raise ValidationError("preparation issues cannot claim the runtime stage")
        runtime_issues = self.issues[prepared_issue_count:]
        if any(item.stage != WorkflowStage.CASE_RUNTIME for item in runtime_issues):
            raise ValidationError("run-added issues must be runtime-stage issues")
        linked_issues = (
            self.issues if runtime_receipt.metadata.get("executed") is False else runtime_issues
        )
        if runtime_receipt.issue_addresses != tuple(item.content_address for item in linked_issues):
            raise ValidationError("runtime receipt issue links do not close")
        if (
            runtime_receipt.warning_count
            != sum(item.severity == WorkflowSeverity.WARNING for item in linked_issues)
            or runtime_receipt.error_count
            != sum(item.severity == WorkflowSeverity.ERROR for item in linked_issues)
            or runtime_receipt.rejected_count != (0 if self.accepted else 1)
        ):
            raise ValidationError("runtime receipt issue counters do not match run evidence")

        manifest = self.prepared.manifest
        manifest_address = self.prepared.manifest_address
        expected_runtime_input = manifest_address or self.prepared.content_address
        if runtime_receipt.input_address != expected_runtime_input:
            raise ValidationError("runtime receipt input_address does not match preparation")
        dossier_address: str | None = None
        run_id: str | None = None
        if self.dossier is not None:
            dossier_address = _dossier_address(self.dossier)
            run_id = self.dossier.run_id
            if manifest is None or manifest_address is None:
                raise ValidationError("a run dossier requires a prepared manifest")
            if self.dossier.case_id != manifest.case_id:
                raise ValidationError("dossier case_id does not match the prepared manifest")
            if self.dossier.input_address != manifest_address:
                raise ValidationError("dossier input_address does not match the prepared manifest")

        if self.run_record is not None:
            record_run_id = self.run_record["run_id"]
            record_input = self.run_record["input_address"]
            record_dossier = self.run_record["dossier_address"]
            if manifest_address is None or record_input != manifest_address:
                raise ValidationError("run record input_address does not match preparation")
            if run_id is not None and record_run_id != run_id:
                raise ValidationError("run record run_id does not match the dossier")
            if dossier_address is not None and record_dossier != dossier_address:
                raise ValidationError("run record dossier_address does not match the dossier")
            run_id = record_run_id

        if self.replay_report is not None:
            replay = self.replay_report
            if manifest_address is None or replay.input_address != manifest_address:
                raise ValidationError("replay input_address does not match preparation")
            if run_id is not None and replay.run_id != run_id:
                raise ValidationError("replay run_id does not match the run bundle")
            if dossier_address is not None and replay.dossier_address != dossier_address:
                raise ValidationError("replay dossier_address does not match the dossier")
            run_id = replay.run_id

        if self.run_record is not None and self.dossier is None:
            raise ValidationError("a run record requires its addressed dossier")
        if self.replay_report is not None and (
            self.dossier is None or self.run_record is None
        ):
            raise ValidationError("a replay report requires its dossier and run record")
        if dossier_address is None:
            if runtime_receipt.output_address is not None:
                raise ValidationError("runtime receipt cannot address an absent dossier")
        elif runtime_receipt.output_address != dossier_address:
            raise ValidationError("runtime receipt output_address does not match dossier")

        metadata_run_id = runtime_receipt.metadata.get("evaluation_run_id")
        if metadata_run_id is not None:
            metadata_run_id = _run_identifier(
                metadata_run_id,
                "runtime receipt evaluation_run_id",
            )
        expected_runtime_source = (
            run_id
            or metadata_run_id
            or self.prepared.run_id
            or "unassigned-run"
        )
        if runtime_receipt.source_id != expected_runtime_source:
            raise ValidationError("runtime receipt source_id does not match run identity")

        if self.accepted:
            assert self.dossier is not None
            assert self.run_record is not None
            assert self.replay_report is not None
            if not (
                self.replay_report.event_chain_valid
                and self.replay_report.stored_dossier_matches_address
            ):
                raise ValidationError("accepted run requires a valid replay proof")
            if (
                runtime_receipt.state != WorkflowState.ACCEPTED
                or runtime_receipt.source_id != self.dossier.run_id
                or runtime_receipt.input_address != manifest_address
                or runtime_receipt.output_address != dossier_address
            ):
                raise ValidationError("runtime receipt does not match the accepted run bundle")
            if self.dossier.dossier_id != f"dos-{self.dossier.run_id}":
                raise ValidationError("dossier_id does not match the accepted run identity")
            if (
                runtime_receipt.record_count != len(self.dossier.hypotheses)
                or runtime_receipt.accepted_count != len(self.dossier.hypotheses)
                or runtime_receipt.rejected_count != 0
            ):
                raise ValidationError("runtime receipt counts do not match the accepted dossier")

            metadata = runtime_receipt.metadata
            if metadata.get("persisted") is not True or metadata.get("replay_valid") is not True:
                raise ValidationError(
                    "accepted runtime receipt requires persisted replay-valid metadata"
                )
            rna_fields = {
                "prepared_run_id",
                "evaluation_run_id",
                "rna_consequence_count",
                "rna_consequence_addresses",
                "rna_input_address",
            }
            has_rna = any(field_name in metadata for field_name in rna_fields)
            if has_rna:
                if set(metadata) != {"persisted", "replay_valid", *rna_fields}:
                    raise ValidationError("accepted RNA runtime metadata is incomplete or unknown")
                if metadata["prepared_run_id"] != self.prepared.run_id:
                    raise ValidationError("runtime prepared_run_id does not match preparation")
                if metadata["evaluation_run_id"] != self.dossier.run_id:
                    raise ValidationError("runtime evaluation_run_id does not match dossier")
                count = _integer(
                    metadata["rna_consequence_count"],
                    "runtime rna_consequence_count",
                )
                addresses = _text_sequence(
                    metadata["rna_consequence_addresses"],
                    "runtime rna_consequence_addresses",
                    allow_empty=False,
                    max_items=MAX_CASE_RNA_CONSEQUENCES,
                )
                addresses = tuple(
                    _rna_consequence_address(item, "runtime RNA consequence address")
                    for item in addresses
                )
                if count != len(addresses) or addresses != tuple(sorted(addresses)):
                    raise ValidationError("runtime RNA consequence metadata is not canonical")
                assert manifest is not None
                digest = content_hash(
                    {
                        "input": manifest.content_address,
                        "requested_by": manifest.requested_by,
                        "rna_consequences": list(addresses),
                    }
                ).split(":", 1)[1]
                expected_evaluation = f"run-{digest[:24]}"
                if self.dossier.run_id != expected_evaluation:
                    raise ValidationError(
                        "runtime RNA addresses do not derive the evaluation run_id"
                    )
                _sha256_address(metadata["rna_input_address"], "runtime rna_input_address")
            else:
                if set(metadata) != {"persisted", "replay_valid"}:
                    raise ValidationError("accepted runtime metadata contains unknown fields")
                if self.dossier.run_id != self.prepared.run_id:
                    raise ValidationError("non-RNA run_id does not match preparation")

    @property
    def accepted(self) -> bool:
        return self.state == WorkflowState.ACCEPTED

    @property
    def blocked(self) -> bool:
        return not self.accepted

    @property
    def run_id(self) -> str | None:
        if self.dossier is not None:
            return self.dossier.run_id
        return self.prepared.run_id

    def _identity_body(self) -> dict[str, Any]:
        self._validate_links()
        return {
            "version": WORKFLOW_VERSION,
            "state": str(self.state),
            "prepared_address": self.prepared.content_address,
            "dossier_address": None if self.dossier is None else self.dossier.content_address,
            "run_record_address": (
                None if self.run_record is None else content_hash(dict(self.run_record))
            ),
            "replay_report": (None if self.replay_report is None else self.replay_report.to_dict()),
            "stage_receipt_addresses": [item.content_address for item in self.stage_receipts],
            "issue_addresses": [item.content_address for item in self.issues],
        }

    @property
    def content_address(self) -> str:
        return content_hash(self._identity_body())

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": WORKFLOW_VERSION,
            "state": str(self.state),
            "accepted": self.accepted,
            "blocked": self.blocked,
            "prepared": self.prepared.to_dict(),
            "dossier": None if self.dossier is None else self.dossier.to_dict(),
            "run_record": None if self.run_record is None else jsonable(dict(self.run_record)),
            "replay_report": (None if self.replay_report is None else self.replay_report.to_dict()),
            "stage_receipts": [item.to_dict() for item in self.stage_receipts],
            "issues": [item.to_dict() for item in self.issues],
            "content_address": self.content_address,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> CaseRunResult:
        raw = _strict_mapping(
            value,
            allowed={
                "version",
                "state",
                "accepted",
                "blocked",
                "prepared",
                "dossier",
                "run_record",
                "replay_report",
                "stage_receipts",
                "issues",
                "content_address",
            },
            required={
                "version",
                "state",
                "accepted",
                "blocked",
                "prepared",
                "dossier",
                "run_record",
                "replay_report",
                "stage_receipts",
                "issues",
                "content_address",
            },
            label="case run result",
        )
        if raw["version"] != WORKFLOW_VERSION:
            raise ValidationError(f"unsupported case run result version: {raw['version']}")
        prepared_raw = raw["prepared"]
        if not isinstance(prepared_raw, Mapping):
            raise ValidationError("run result prepared field must be an object")
        dossier_raw = raw["dossier"]
        if dossier_raw is not None and not isinstance(dossier_raw, Mapping):
            raise ValidationError("run result dossier must be an object or null")
        dossier = None if dossier_raw is None else _strict_dossier(dossier_raw)
        run_raw = raw["run_record"]
        if run_raw is not None and not isinstance(run_raw, Mapping):
            raise ValidationError("run_record must be an object or null")
        replay_raw = raw["replay_report"]
        replay = None if replay_raw is None else _replay_from_mapping(replay_raw)
        result = cls(
            state=raw["state"],
            prepared=PreparedCase.from_mapping(prepared_raw),
            dossier=dossier,
            run_record=None if run_raw is None else dict(run_raw),
            replay_report=replay,
            stage_receipts=tuple(
                StageReceipt.from_mapping(item)
                for item in _sequence(raw["stage_receipts"], "stage_receipts")
            ),
            issues=tuple(
                WorkflowIssue.from_mapping(item) for item in _sequence(raw["issues"], "issues")
            ),
        )
        if type(raw["accepted"]) is not bool or type(raw["blocked"]) is not bool:
            raise ValidationError("run accepted and blocked fields must be booleans")
        if raw["accepted"] != result.accepted or raw["blocked"] != result.blocked:
            raise ValidationError("run state flags are inconsistent")
        _verify_address(raw, result.content_address, "case run result")
        return result

    def public_summary(self) -> dict[str, Any]:
        """Return a stable, payload-free run summary."""

        counts = Counter(str(issue.severity) for issue in self.issues)
        return {
            "version": WORKFLOW_VERSION,
            "state": str(self.state),
            "accepted": self.accepted,
            "blocked": self.blocked,
            "case_id": (
                self.dossier.case_id
                if self.dossier is not None
                else (None if self.prepared.manifest is None else self.prepared.manifest.case_id)
            ),
            "run_id": self.run_id,
            "manifest_address": self.prepared.manifest_address,
            "dossier_address": (None if self.dossier is None else self.dossier.content_address),
            "workflow_address": self.content_address,
            "hypothesis_count": 0 if self.dossier is None else len(self.dossier.hypotheses),
            "evidence_count": 0 if self.dossier is None else len(self.dossier.evidence),
            "experiment_count": 0 if self.dossier is None else len(self.dossier.experiments),
            "replay_valid": bool(
                self.replay_report is not None
                and self.replay_report.event_chain_valid
                and self.replay_report.stored_dossier_matches_address
            ),
            "stage_receipt_addresses": [item.content_address for item in self.stage_receipts],
            "issue_counts": {
                "warning": counts[WorkflowSeverity.WARNING.value],
                "error": counts[WorkflowSeverity.ERROR.value],
            },
            "issue_codes": sorted({item.code for item in self.issues}),
        }


RunCaseResult = CaseRunResult


def _replay_from_mapping(value: object) -> ReplayReport:
    if not isinstance(value, Mapping):
        raise ValidationError("replay_report must be an object")
    raw = _strict_mapping(
        value,
        allowed={
            "run_id",
            "event_chain_valid",
            "input_address",
            "dossier_address",
            "stored_dossier_matches_address",
            "warnings",
        },
        required={
            "run_id",
            "event_chain_valid",
            "input_address",
            "dossier_address",
            "stored_dossier_matches_address",
            "warnings",
        },
        label="replay report",
    )
    if (
        type(raw["event_chain_valid"]) is not bool
        or type(raw["stored_dossier_matches_address"]) is not bool
    ):
        raise ValidationError("replay validity fields must be booleans")
    return ReplayReport(
        run_id=_run_identifier(raw["run_id"], "replay run_id"),
        event_chain_valid=raw["event_chain_valid"],
        input_address=_sha256_address(raw["input_address"], "replay input_address"),
        dossier_address=_sha256_address(raw["dossier_address"], "replay dossier_address"),
        stored_dossier_matches_address=raw["stored_dossier_matches_address"],
        warnings=_text_sequence(raw["warnings"], "replay warnings", allow_empty=True),
    )


def _run_id(manifest: CaseManifest) -> str:
    digest = content_hash(
        {"input": manifest.content_address, "requested_by": manifest.requested_by}
    ).split(":", 1)[1]
    return f"run-{digest[:24]}"


def _same_build(left: str, right: str) -> bool:
    return left.strip().casefold() == right.strip().casefold()


def _has_errors(issues: Iterable[WorkflowIssue]) -> bool:
    return any(issue.severity == WorkflowSeverity.ERROR for issue in issues)


def _intake_issues(batch: IntakeBatch) -> tuple[WorkflowIssue, ...]:
    return tuple(
        WorkflowIssue(
            code=issue.code,
            severity=(
                WorkflowSeverity.ERROR
                if issue.severity == IntakeSeverity.ERROR
                else WorkflowSeverity.WARNING
            ),
            stage=WorkflowStage.VARIANT_INTAKE,
            message=issue.message,
            source_id=batch.source_id,
            line_number=issue.line_number,
            raw_hash=issue.raw_hash,
            remediation=issue.remediation,
        )
        for issue in batch.issues
    )


def _track_issues(batch: RegulatoryTrackBatch) -> tuple[WorkflowIssue, ...]:
    return tuple(
        WorkflowIssue(
            code=issue.code,
            severity=(
                WorkflowSeverity.ERROR
                if issue.severity == TrackIssueSeverity.ERROR
                else WorkflowSeverity.WARNING
            ),
            stage=WorkflowStage.REGULATORY_TRACK,
            message=issue.message,
            source_id=batch.source_id,
            line_number=issue.line_number,
            raw_hash=issue.raw_hash,
            remediation=issue.remediation,
        )
        for issue in batch.issues
    )


def _variant_batch_address(batch: IntakeBatch, source: VariantSource) -> str:
    receipt = batch.receipt.provenance_dict()
    return content_hash(
        {
            "version": WORKFLOW_VERSION,
            "source_id": source.source_id,
            "input_format": str(source.input_format),
            "declared_genome_build": source.genome_build,
            "sample_id": source.sample_id,
            "include_no_call": source.include_no_call,
            "source_metadata": jsonable(dict(source.metadata)),
            "receipt": receipt,
            "variants": [item.to_dict() for item in batch.variants],
            "deferred_records": [item.to_dict() for item in batch.deferred_records],
            "issues": [item.to_dict() for item in batch.issues],
        }
    )


def _variant_receipt(
    source: VariantSource,
    batch: IntakeBatch | None,
    issues: tuple[WorkflowIssue, ...],
    *,
    observed_at: str,
) -> StageReceipt:
    if batch is None:
        return StageReceipt(
            stage=WorkflowStage.VARIANT_INTAKE,
            state=WorkflowState.BLOCKED,
            source_id=source.source_id,
            input_address=source.input_address,
            output_address=None,
            observed_at=observed_at,
            error_count=sum(item.severity == WorkflowSeverity.ERROR for item in issues),
            warning_count=sum(item.severity == WorkflowSeverity.WARNING for item in issues),
            issue_addresses=tuple(item.content_address for item in issues),
            metadata={
                "input_format": str(source.input_format),
                "genome_build": source.genome_build,
            },
        )
    output_address = _variant_batch_address(batch, source)
    return StageReceipt(
        stage=WorkflowStage.VARIANT_INTAKE,
        state=(WorkflowState.BLOCKED if _has_errors(issues) else WorkflowState.ACCEPTED),
        source_id=source.source_id,
        input_address=batch.receipt.input_hash,
        output_address=output_address,
        observed_at=batch.receipt.created_at,
        record_count=batch.receipt.record_count,
        accepted_count=batch.receipt.accepted_count,
        rejected_count=batch.receipt.rejected_count,
        warning_count=sum(item.severity == WorkflowSeverity.WARNING for item in issues),
        error_count=sum(item.severity == WorkflowSeverity.ERROR for item in issues),
        issue_addresses=tuple(item.content_address for item in issues),
        metadata={
            "input_format": str(source.input_format),
            "genome_build": source.genome_build,
            "header_address": batch.receipt.header_hash,
            "intake_receipt_address": batch.receipt.content_address,
        },
    )


def _parse_variant(source: VariantSource) -> IntakeBatch:
    parser = VariantIntake(default_build=source.genome_build)
    if source.input_format == IntakeFormat.BCF:
        if not isinstance(source.payload, bytes):
            raise ValidationError("BCF input requires an in-memory bytes payload")
        return parser.parse_bytes(
            source.payload,
            source_id=source.source_id,
            genome_build=source.genome_build,
            sample_id=source.sample_id,
            include_no_call=source.include_no_call,
        )
    text = _decode_payload(source.payload, "variant source")
    return parser.parse_text(
        text,
        source_id=source.source_id,
        input_format=source.input_format,
        genome_build=source.genome_build,
        sample_id=source.sample_id,
        include_no_call=source.include_no_call,
    )


def _track_sort_key(source: RegulatoryTrackSource) -> tuple[str, ...]:
    assert isinstance(source.context, ReferenceContext)
    return (
        source.source_id,
        str(source.input_format),
        source.genome_build,
        source.context.key,
        source.input_address,
        content_hash(dict(source.metadata)),
        content_hash(source.target_gene_keys),
    )


def _track_output_address(
    batch: RegulatoryTrackBatch,
    source: RegulatoryTrackSource,
    elements: tuple[CandidateElement, ...],
) -> str:
    assert isinstance(source.context, ReferenceContext)
    return _candidate_output_address(
        batch_address=batch.content_address,
        context=source.context,
        source_metadata=source.metadata,
        target_gene_keys=source.target_gene_keys,
        elements=elements,
    )


def _parse_track(
    source: RegulatoryTrackSource,
) -> tuple[RegulatoryTrackBatch, tuple[CandidateElement, ...]]:
    text = _decode_payload(source.payload, "regulatory track source")
    batch = RegulatoryTrackParser().parse_text(
        text,
        source_id=source.source_id,
        genome_build=source.genome_build,
        input_format=source.input_format,
    )
    assert isinstance(source.context, ReferenceContext)
    return batch, batch.to_candidate_elements(
        source.context, target_gene_keys=source.target_gene_keys
    )


def _track_receipt(
    source: RegulatoryTrackSource,
    batch: RegulatoryTrackBatch | None,
    elements: tuple[CandidateElement, ...],
    issues: tuple[WorkflowIssue, ...],
    *,
    observed_at: str,
) -> StageReceipt:
    if batch is None:
        return StageReceipt(
            stage=WorkflowStage.REGULATORY_TRACK,
            state=WorkflowState.BLOCKED,
            source_id=source.source_id,
            input_address=source.input_address,
            output_address=None,
            observed_at=observed_at,
            warning_count=sum(item.severity == WorkflowSeverity.WARNING for item in issues),
            error_count=sum(item.severity == WorkflowSeverity.ERROR for item in issues),
            issue_addresses=tuple(item.content_address for item in issues),
            metadata={
                "input_format": str(source.input_format),
                "genome_build": source.genome_build,
            },
        )
    output_address = _track_output_address(batch, source, elements)
    return StageReceipt(
        stage=WorkflowStage.REGULATORY_TRACK,
        state=(WorkflowState.BLOCKED if _has_errors(issues) else WorkflowState.ACCEPTED),
        source_id=source.source_id,
        input_address=batch.input_hash,
        output_address=output_address,
        observed_at=observed_at,
        record_count=len(batch.features) + len(batch.errors),
        accepted_count=len(batch.features),
        rejected_count=len(batch.errors),
        warning_count=sum(item.severity == WorkflowSeverity.WARNING for item in issues),
        error_count=sum(item.severity == WorkflowSeverity.ERROR for item in issues),
        issue_addresses=tuple(item.content_address for item in issues),
        metadata={
            "input_format": str(source.input_format),
            "genome_build": source.genome_build,
            "context_key": source.context.key,  # type: ignore[union-attr]
            "header_address": batch.header_hash,
            "track_batch_address": batch.content_address,
        },
    )


def prepare_case(
    *,
    case_id: str,
    subject_id: str,
    context: ReferenceContext | Mapping[str, Any],
    variant_source: VariantSource | Mapping[str, Any],
    regulatory_tracks: Iterable[RegulatoryTrackSource | Mapping[str, Any]] = (),
    tracks: Iterable[RegulatoryTrackSource | Mapping[str, Any]] | None = None,
    metadata: Mapping[str, Any] | None = None,
    requested_by: str = "unspecified",
    live_reference: bool = False,
) -> PreparedCase:
    """Prepare a canonical case from inline sources and apply every hard gate."""

    case_id = _required_text(case_id, "case_id")
    subject_id = _required_text(subject_id, "subject_id")
    requested_by = _required_text(requested_by, "requested_by")
    if type(live_reference) is not bool:
        raise ValidationError("live_reference must be a boolean")
    case_context = _context(context, "case context")
    source = (
        variant_source
        if isinstance(variant_source, VariantSource)
        else VariantSource.from_mapping(variant_source)
    )
    declared_tracks = _bounded_regulatory_tracks(regulatory_tracks, "regulatory_tracks")
    alias_tracks = () if tracks is None else _bounded_regulatory_tracks(tracks, "tracks")
    if declared_tracks and alias_tracks:
        raise ValidationError("use regulatory_tracks or tracks, not both")
    track_values = alias_tracks or declared_tracks
    normalized_tracks = tuple(
        item
        if isinstance(item, RegulatoryTrackSource)
        else RegulatoryTrackSource.from_mapping(item)
        for item in track_values
    )
    normalized_tracks = tuple(sorted(normalized_tracks, key=_track_sort_key))
    user_metadata = (
        _FrozenJsonObject() if metadata is None else _json_mapping(metadata, "case metadata")
    )
    reserved_metadata = sorted(_RESERVED_CASE_METADATA_KEYS & set(user_metadata))
    if reserved_metadata:
        raise ValidationError(f"case metadata contains reserved keys: {reserved_metadata}")
    observed_at = utc_now().isoformat()

    issues: list[WorkflowIssue] = []
    receipts: list[StageReceipt] = []
    source_ids = [source.source_id, *(item.source_id for item in normalized_tracks)]
    duplicate_sources = sorted(item for item, count in Counter(source_ids).items() if count > 1)
    if duplicate_sources:
        issues.append(
            WorkflowIssue(
                code="duplicate_source_id",
                severity=WorkflowSeverity.ERROR,
                stage=WorkflowStage.MANIFEST,
                message=f"source IDs must be unique: {duplicate_sources}",
                remediation="Assign a stable, distinct source_id to every declared payload.",
            )
        )

    variant_gate: list[WorkflowIssue] = []
    if not _same_build(source.genome_build, case_context.genome_build):
        variant_gate.append(
            WorkflowIssue(
                code="genome_build_mismatch",
                severity=WorkflowSeverity.ERROR,
                stage=WorkflowStage.VARIANT_INTAKE,
                message=(
                    f"variant source build {source.genome_build!r} does not match "
                    f"case build {case_context.genome_build!r}"
                ),
                source_id=source.source_id,
                remediation="Normalize variants to the case genome build before preparation.",
            )
        )
    variant_batch: IntakeBatch | None = None
    try:
        variant_batch = _parse_variant(source)
        variant_gate.extend(_intake_issues(variant_batch))
        for variant in variant_batch.variants:
            if not _same_build(variant.genome_build, case_context.genome_build):
                variant_gate.append(
                    WorkflowIssue(
                        code="genome_build_mismatch",
                        severity=WorkflowSeverity.ERROR,
                        stage=WorkflowStage.VARIANT_INTAKE,
                        message=(
                            f"variant {variant.variant_id!r} uses build {variant.genome_build!r}; "
                            f"expected {case_context.genome_build!r}"
                        ),
                        source_id=source.source_id,
                        remediation="Normalize every input row to the declared case genome build.",
                    )
                )
    except (GlioError, UnicodeError, ValueError, TypeError) as exc:
        variant_gate.append(
            WorkflowIssue(
                code="intake_error",
                severity=WorkflowSeverity.ERROR,
                stage=WorkflowStage.VARIANT_INTAKE,
                message=str(exc),
                source_id=source.source_id,
                remediation="Correct the inline variant payload and its explicit format metadata.",
            )
        )
    issues.extend(variant_gate)
    receipts.append(
        _variant_receipt(source, variant_batch, tuple(variant_gate), observed_at=observed_at)
    )

    candidates: list[CandidateElement] = []
    candidate_limit_exceeded = False
    track_provenance: list[dict[str, Any]] = []
    for track in normalized_tracks:
        track_gate: list[WorkflowIssue] = []
        assert isinstance(track.context, ReferenceContext)
        if not _same_build(track.genome_build, case_context.genome_build):
            track_gate.append(
                WorkflowIssue(
                    code="genome_build_mismatch",
                    severity=WorkflowSeverity.ERROR,
                    stage=WorkflowStage.REGULATORY_TRACK,
                    message=(
                        f"track {track.source_id!r} build {track.genome_build!r} does not match "
                        f"case build {case_context.genome_build!r}"
                    ),
                    source_id=track.source_id,
                    remediation="Provide a track normalized to the case genome build.",
                )
            )
        if not _same_build(track.context.genome_build, track.genome_build):
            track_gate.append(
                WorkflowIssue(
                    code="genome_build_mismatch",
                    severity=WorkflowSeverity.ERROR,
                    stage=WorkflowStage.REGULATORY_TRACK,
                    message=(
                        f"track context build {track.context.genome_build!r} does not match "
                        f"its declared build {track.genome_build!r}"
                    ),
                    source_id=track.source_id,
                    remediation="Align the track context and source assembly declarations.",
                )
            )
        batch: RegulatoryTrackBatch | None = None
        elements: tuple[CandidateElement, ...] = ()
        if candidate_limit_exceeded:
            track_gate.append(
                WorkflowIssue(
                    code="candidate_element_limit_exceeded",
                    severity=WorkflowSeverity.ERROR,
                    stage=WorkflowStage.REGULATORY_TRACK,
                    message=(
                        f"track {track.source_id!r} was not parsed after the aggregate "
                        f"candidate-element ceiling of {MAX_CASE_CANDIDATE_ELEMENTS} "
                        "was exceeded"
                    ),
                    source_id=track.source_id,
                    remediation=(
                        "Reduce or partition the declared regulatory tracks before case "
                        "preparation."
                    ),
                )
            )
        else:
            try:
                batch, parsed_elements = _parse_track(track)
                track_gate.extend(_track_issues(batch))
                if len(candidates) + len(parsed_elements) > MAX_CASE_CANDIDATE_ELEMENTS:
                    candidate_limit_exceeded = True
                    track_gate.append(
                        WorkflowIssue(
                            code="candidate_element_limit_exceeded",
                            severity=WorkflowSeverity.ERROR,
                            stage=WorkflowStage.REGULATORY_TRACK,
                            message=(
                                "aggregate candidate-element ceiling of "
                                f"{MAX_CASE_CANDIDATE_ELEMENTS} was exceeded while parsing "
                                f"track {track.source_id!r}"
                            ),
                            source_id=track.source_id,
                            remediation=(
                                "Reduce or partition the declared regulatory tracks before "
                                "case preparation."
                            ),
                        )
                    )
                else:
                    elements = parsed_elements
                    candidates.extend(elements)
            except (GlioError, UnicodeError, ValueError, TypeError) as exc:
                track_gate.append(
                    WorkflowIssue(
                        code="regulatory_track_error",
                        severity=WorkflowSeverity.ERROR,
                        stage=WorkflowStage.REGULATORY_TRACK,
                        message=str(exc),
                        source_id=track.source_id,
                        remediation=("Correct the inline track payload and its explicit metadata."),
                    )
                )
        issues.extend(track_gate)
        receipt = _track_receipt(
            track,
            batch,
            elements,
            tuple(track_gate),
            observed_at=observed_at,
        )
        receipts.append(receipt)
        if batch is not None:
            track_provenance.append(
                {
                    "source_id": track.source_id,
                    "input_format": str(track.input_format),
                    "genome_build": track.genome_build,
                    "context": track.context.to_dict(),
                    "context_key": track.context.key,
                    "input_address": batch.input_hash,
                    "batch_address": batch.content_address,
                    "candidate_address": receipt.output_address,
                    "feature_count": len(batch.features),
                    "source_metadata": jsonable(dict(track.metadata)),
                    "target_gene_keys": list(track.target_gene_keys),
                }
            )

    variants = (
        ()
        if variant_batch is None
        else tuple(
            sorted(
                variant_batch.variants,
                key=lambda item: (item.canonical_key, item.variant_id),
            )
        )
    )
    candidates_tuple = tuple(
        sorted(candidates, key=_candidate_sort_key)
    )
    variant_ids = [item.variant_id for item in variants]
    duplicate_variants = sorted(item for item, count in Counter(variant_ids).items() if count > 1)
    if duplicate_variants:
        issues.append(
            WorkflowIssue(
                code="duplicate_variant_id",
                severity=WorkflowSeverity.ERROR,
                stage=WorkflowStage.MANIFEST,
                message=f"variant IDs must be unique: {duplicate_variants}",
                remediation="Assign a unique ID to every canonical variant.",
            )
        )
    element_ids = [item.element_id for item in candidates_tuple]
    duplicate_elements = sorted(item for item, count in Counter(element_ids).items() if count > 1)
    if duplicate_elements:
        issues.append(
            WorkflowIssue(
                code="duplicate_element_id",
                severity=WorkflowSeverity.ERROR,
                stage=WorkflowStage.MANIFEST,
                message=f"candidate element IDs must be unique: {duplicate_elements}",
                remediation="Namespace or deduplicate feature IDs before case preparation.",
            )
        )
    if not variants:
        issues.append(
            WorkflowIssue(
                code="no_variants",
                severity=WorkflowSeverity.ERROR,
                stage=WorkflowStage.MANIFEST,
                message="variant intake produced no executable canonical variants",
                source_id=source.source_id,
                remediation="Supply at least one supported, non-reference variant.",
            )
        )
    if not candidates_tuple and not live_reference:
        issues.append(
            WorkflowIssue(
                code="no_candidate_elements",
                severity=WorkflowSeverity.ERROR,
                stage=WorkflowStage.MANIFEST,
                message="no candidate regulatory elements were produced",
                remediation=(
                    "Supply a valid regulatory track or enable live_reference "
                    "enrichment explicitly."
                ),
            )
        )
    try:
        _validate_case_runtime_work(variants, candidates_tuple, label="prepared case")
    except ValidationError as exc:
        issues.append(
            WorkflowIssue(
                code="case_runtime_work_limit_exceeded",
                severity=WorkflowSeverity.ERROR,
                stage=WorkflowStage.MANIFEST,
                message=str(exc),
                remediation=(
                    "Reduce or partition variants, candidate elements, target genes, or state "
                    "IDs before case preparation."
                ),
            )
        )

    variant_output = receipts[0].output_address
    manifest_input_address = content_hash(
        {
            "version": WORKFLOW_VERSION,
            "case_id": case_id,
            "subject_id": subject_id,
            "requested_by": requested_by,
            "context": case_context.to_dict(),
            "variant_output_address": variant_output,
            "track_output_addresses": [item.output_address for item in receipts[1:]],
            "metadata": user_metadata,
            "live_reference": live_reference,
        }
    )
    manifest: CaseManifest | None = None
    run_id: str | None = None
    if not _has_errors(issues):
        assert variant_batch is not None
        intake_receipt = variant_batch.receipt.provenance_dict()
        provenance = {
            "version": WORKFLOW_VERSION,
            "identity_policy": "observational timestamps excluded",
            "variant_source": {
                "source_id": source.source_id,
                "input_format": str(source.input_format),
                "genome_build": source.genome_build,
                "input_address": variant_batch.receipt.input_hash,
                "batch_address": variant_output,
                "intake_receipt": intake_receipt,
                "source_metadata": jsonable(dict(source.metadata)),
            },
            "regulatory_tracks": track_provenance,
            "canonical_order": {
                "tracks": "source_id, format, build, context, payload address",
                "variants": "canonical_key, variant_id",
                "candidate_elements": "element_id, source_id, chromosome, start, end",
            },
            "live_reference": live_reference,
        }
        manifest_metadata = dict(user_metadata)
        manifest_metadata["case_workflow_provenance"] = provenance
        input_versions = {source.source_id: variant_batch.receipt.input_hash}
        input_versions.update(
            {item["source_id"]: item["input_address"] for item in track_provenance}
        )
        try:
            canonical_variants = tuple(
                _variant_identity(item, f"manifest variant {index}")
                for index, item in enumerate(variants)
            )
            canonical_candidates = tuple(
                _candidate_element(item, f"manifest candidate element {index}")
                for index, item in enumerate(candidates_tuple)
            )
            manifest = CaseManifest(
                case_id=case_id,
                subject_id=subject_id,
                context=case_context,
                variants=canonical_variants,
                candidate_elements=canonical_candidates,
                metadata=_json_mapping(manifest_metadata, "manifest metadata"),
                input_versions=_text_mapping(
                    dict(sorted(input_versions.items())),
                    "manifest input_versions",
                ),
                requested_by=requested_by,
            )
            # Force serialization here so a non-canonical manifest never reaches runtime.
            _ = manifest.content_address
            run_id = _run_id(manifest)
        except (GlioError, TypeError, ValueError) as exc:
            issues.append(
                WorkflowIssue(
                    code="manifest_error",
                    severity=WorkflowSeverity.ERROR,
                    stage=WorkflowStage.MANIFEST,
                    message=str(exc),
                    remediation="Correct the case declarations before execution.",
                )
            )
            manifest = None
            run_id = None

    accepted = manifest is not None and not _has_errors(issues)
    manifest_receipt = StageReceipt(
        stage=WorkflowStage.MANIFEST,
        state=WorkflowState.ACCEPTED if accepted else WorkflowState.BLOCKED,
        source_id=case_id,
        input_address=manifest_input_address,
        output_address=None if manifest is None else manifest.content_address,
        observed_at=observed_at,
        record_count=len(variants) + len(candidates_tuple),
        accepted_count=(len(variants) + len(candidates_tuple) if accepted else 0),
        rejected_count=(
            0 if accepted else sum(item.severity == WorkflowSeverity.ERROR for item in issues)
        ),
        warning_count=sum(item.severity == WorkflowSeverity.WARNING for item in issues),
        error_count=sum(item.severity == WorkflowSeverity.ERROR for item in issues),
        issue_addresses=tuple(item.content_address for item in issues),
        metadata={
            "variant_count": len(variants),
            "candidate_element_count": len(candidates_tuple),
            "track_count": len(normalized_tracks),
            "live_reference": live_reference,
        },
    )
    receipts.append(manifest_receipt)
    return PreparedCase(
        state=WorkflowState.ACCEPTED if accepted else WorkflowState.BLOCKED,
        manifest=manifest if accepted else None,
        run_id=run_id if accepted else None,
        live_reference=live_reference,
        stage_receipts=tuple(receipts),
        issues=tuple(issues),
    )


def run_case(
    prepared: PreparedCase | Mapping[str, Any],
    *,
    data_root: str | Path = ".glio",
    runtime: CaseRuntime | None = None,
    rna_consequences: Iterable[RNAConsequenceEvidence | Mapping[str, Any]] = (),
) -> CaseRunResult:
    """Execute accepted preparation with optional matched-RNA consequences."""

    value = PreparedCase.from_mapping(
        prepared.to_dict() if isinstance(prepared, PreparedCase) else prepared
    )
    issues = list(value.issues)
    receipts = list(value.stage_receipts)
    observed_at = utc_now().isoformat()
    manifest_address = value.manifest_address or value.content_address
    rna_rows: tuple[RNAConsequenceEvidence, ...] = ()
    rna_input_blocked = False
    try:
        rna_rows = _normalize_rna_consequences(rna_consequences)
    except (GlioError, OverflowError, TypeError, ValueError) as exc:
        rna_input_blocked = True
        issues.append(
            WorkflowIssue(
                code="invalid_rna_consequence",
                severity=WorkflowSeverity.ERROR,
                stage=WorkflowStage.CASE_RUNTIME,
                message=str(exc),
                remediation=(
                    "Supply canonical RNAConsequenceEvidence objects or strict mappings "
                    "with valid content addresses."
                ),
            )
        )

    evaluation_run_id = value.run_id
    if value.manifest is not None and not rna_input_blocked:
        evaluation_run_id = CaseRuntime._run_id(value.manifest, rna_rows)

    if not value.accepted or value.manifest is None or value.run_id is None or rna_input_blocked:
        blocked_metadata: dict[str, Any] = {
            "executed": False,
            "reason": ("invalid_rna_consequence" if rna_input_blocked else "preparation_blocked"),
        }
        if rna_rows:
            blocked_metadata.update(
                {
                    "rna_consequence_count": len(rna_rows),
                    "rna_consequence_addresses": [item.content_address for item in rna_rows],
                }
            )
        receipts.append(
            StageReceipt(
                stage=WorkflowStage.CASE_RUNTIME,
                state=WorkflowState.BLOCKED,
                source_id=evaluation_run_id or "unassigned-run",
                input_address=manifest_address,
                output_address=None,
                observed_at=observed_at,
                rejected_count=1,
                warning_count=sum(item.severity == WorkflowSeverity.WARNING for item in issues),
                error_count=sum(item.severity == WorkflowSeverity.ERROR for item in issues),
                issue_addresses=tuple(item.content_address for item in issues),
                metadata=blocked_metadata,
            )
        )
        return CaseRunResult(
            state=WorkflowState.BLOCKED,
            prepared=value,
            dossier=None,
            run_record=None,
            replay_report=None,
            stage_receipts=tuple(receipts),
            issues=tuple(issues),
        )

    runtime_manifest_address = value.manifest_address
    assert runtime_manifest_address is not None
    assert evaluation_run_id is not None
    dossier: Dossier | None = None
    run_record: Mapping[str, Any] | None = None
    replay: ReplayReport | None = None
    rna_input_address: str | None = None
    try:
        engine = runtime or CaseRuntime(data_root)
        dossier = engine.evaluate(
            value.manifest,
            live_reference=value.live_reference,
            rna_consequences=rna_rows,
        )
        run_record = engine.get_run(dossier.run_id)
        event_record = engine.store.store.get(str(run_record["event_address"]))
        rna_input_address = _runtime_rna_input_address(event_record)
        stored_dossier = engine.get_dossier(str(run_record["dossier_address"]))
        replay = ReplayVerifier().verify(dict(run_record), event_record, stored_dossier)
        if dossier.run_id != evaluation_run_id:
            issues.append(
                WorkflowIssue(
                    code="run_identity_mismatch",
                    severity=WorkflowSeverity.ERROR,
                    stage=WorkflowStage.CASE_RUNTIME,
                    message=(
                        "runtime run_id does not match the expected manifest and RNA "
                        "evaluation identity"
                    ),
                    remediation=(
                        "Do not execute a manifest or RNA consequence through an "
                        "identity-mutating adapter."
                    ),
                )
            )
        if str(run_record.get("input_address")) != runtime_manifest_address:
            issues.append(
                WorkflowIssue(
                    code="persisted_input_mismatch",
                    severity=WorkflowSeverity.ERROR,
                    stage=WorkflowStage.CASE_RUNTIME,
                    message="persisted input address does not match the prepared manifest",
                    remediation="Inspect the run store before using the dossier.",
                )
            )
        if not replay.event_chain_valid or not replay.stored_dossier_matches_address:
            issues.append(
                WorkflowIssue(
                    code="replay_integrity_error",
                    severity=WorkflowSeverity.ERROR,
                    stage=WorkflowStage.CASE_RUNTIME,
                    message="persisted run failed event-chain or dossier-address verification",
                    remediation=(
                        "Quarantine the run and inspect its immutable objects and event chain."
                    ),
                )
            )
    except (GlioError, OSError, KeyError, TypeError, ValueError) as exc:
        issues.append(
            WorkflowIssue(
                code=getattr(exc, "code", "runtime_error"),
                severity=WorkflowSeverity.ERROR,
                stage=WorkflowStage.CASE_RUNTIME,
                message=str(exc),
                remediation="Resolve the runtime or persistence error, then replay preparation.",
            )
        )

    runtime_issues = tuple(item for item in issues if item.stage == WorkflowStage.CASE_RUNTIME)
    accepted = dossier is not None and replay is not None and not _has_errors(runtime_issues)
    runtime_metadata: dict[str, Any] = {
        "persisted": run_record is not None,
        "replay_valid": bool(
            replay is not None
            and replay.event_chain_valid
            and replay.stored_dossier_matches_address
        ),
    }
    if rna_rows:
        runtime_metadata.update(
            {
                "prepared_run_id": value.run_id,
                "evaluation_run_id": evaluation_run_id,
                "rna_consequence_count": len(rna_rows),
                "rna_consequence_addresses": [item.content_address for item in rna_rows],
            }
        )
        if rna_input_address is not None:
            runtime_metadata["rna_input_address"] = rna_input_address
    receipts.append(
        StageReceipt(
            stage=WorkflowStage.CASE_RUNTIME,
            state=WorkflowState.ACCEPTED if accepted else WorkflowState.BLOCKED,
            source_id=evaluation_run_id,
            input_address=runtime_manifest_address,
            output_address=None if dossier is None else dossier.content_address,
            observed_at=(dossier.created_at if dossier is not None else observed_at),
            record_count=0 if dossier is None else len(dossier.hypotheses),
            accepted_count=0 if not accepted or dossier is None else len(dossier.hypotheses),
            rejected_count=0 if accepted else 1,
            warning_count=sum(item.severity == WorkflowSeverity.WARNING for item in runtime_issues),
            error_count=sum(item.severity == WorkflowSeverity.ERROR for item in runtime_issues),
            issue_addresses=tuple(item.content_address for item in runtime_issues),
            metadata=runtime_metadata,
        )
    )
    return CaseRunResult(
        state=WorkflowState.ACCEPTED if accepted else WorkflowState.BLOCKED,
        prepared=value,
        dossier=dossier,
        run_record=run_record,
        replay_report=replay,
        stage_receipts=tuple(receipts),
        issues=tuple(issues),
    )


def _schema_fragment(schema: Mapping[str, Any]) -> dict[str, Any]:
    """Embed a schema without creating a duplicate URI-identified resource."""

    return {key: value for key, value in schema.items() if key not in {"$schema", "$id"}}


def _non_empty_text_schema() -> dict[str, Any]:
    """Return the whitespace-aware text contract used by runtime normalization."""

    return {"type": "string", "minLength": 1, "pattern": r"\S"}


def _nullable_text_schema() -> dict[str, Any]:
    return {"type": ["string", "null"], "minLength": 1, "pattern": r"\S"}


def _sha256_address_schema(*, nullable: bool = False) -> dict[str, Any]:
    return {
        "type": ["string", "null"] if nullable else "string",
        "pattern": r"^sha256:[0-9a-f]{64}$",
    }


def _run_id_schema(*, nullable: bool = False) -> dict[str, Any]:
    return {
        "type": ["string", "null"] if nullable else "string",
        "pattern": r"^run-[0-9a-f]{24}$",
    }


def _text_array_schema(
    *,
    min_items: int = 0,
    max_items: int | None = None,
    address_items: bool = False,
) -> dict[str, Any]:
    schema: dict[str, Any] = {
        "type": "array",
        "minItems": min_items,
        "uniqueItems": True,
        "items": (
            _sha256_address_schema() if address_items else _non_empty_text_schema()
        ),
    }
    if max_items is not None:
        schema["maxItems"] = max_items
    return schema


def _reference_context_schema(*, persisted: bool) -> dict[str, Any]:
    properties = {
        "genome_build": _non_empty_text_schema(),
        "disease_class": _non_empty_text_schema(),
        "age_group": _non_empty_text_schema(),
        "cell_state": _non_empty_text_schema(),
        "territory": _non_empty_text_schema() | {"default": "unknown"},
        "treatment_phase": _non_empty_text_schema() | {"default": "unknown"},
        "assay_support": _text_array_schema() | {"default": []},
        "source_version": _non_empty_text_schema() | {"default": "unspecified"},
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": sorted(_CONTEXT_FIELDS if persisted else _CONTEXT_REQUIRED_FIELDS),
        "properties": properties,
    }


def _variant_identity_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": sorted(_VARIANT_FIELDS),
        "properties": {
            "variant_id": _non_empty_text_schema(),
            "kind": {"enum": [item.value for item in VariantKind]},
            "chromosome": _non_empty_text_schema(),
            "start": {"type": "integer", "minimum": 1},
            "end": {"type": "integer", "minimum": 1},
            "reference": _non_empty_text_schema(),
            "alternate": _non_empty_text_schema(),
            "genome_build": _non_empty_text_schema(),
            "origin": {"enum": [item.value for item in VariantOrigin]},
            "clonality": _non_empty_text_schema(),
            "sample_id": _non_empty_text_schema(),
            "annotations": {"type": "object"},
        },
        "x-runtime-relations": ["end must be greater than or equal to start"],
    }


def _candidate_element_schema() -> dict[str, Any]:
    target_genes = _text_array_schema(max_items=MAX_CASE_TARGETS_PER_ELEMENT)
    state_ids = _text_array_schema(max_items=MAX_CASE_TARGETS_PER_ELEMENT)
    return {
        "type": "object",
        "additionalProperties": False,
        "required": sorted(_ELEMENT_FIELDS),
        "properties": {
            "element_id": _non_empty_text_schema(),
            "chromosome": _non_empty_text_schema(),
            "start": {"type": "integer", "minimum": 1},
            "end": {"type": "integer", "minimum": 1},
            "element_type": _non_empty_text_schema(),
            "context": _reference_context_schema(persisted=True),
            "source_id": _non_empty_text_schema(),
            "target_genes": target_genes,
            "state_ids": state_ids,
            "features": {
                "type": "object",
                "propertyNames": {"pattern": r"\S"},
                "additionalProperties": {
                    "type": "number",
                    "x-python-runtime-type": "finite-int-or-float",
                },
            },
            "annotations": {"type": "object"},
        },
        "anyOf": [
            {
                "properties": {"target_genes": target_genes | {"minItems": 1}},
                "required": ["target_genes"],
            },
            {
                "properties": {"state_ids": state_ids | {"minItems": 1}},
                "required": ["state_ids"],
            },
        ],
        "x-runtime-relations": [
            "end must be greater than or equal to start",
            "feature values must be finite Python integers or floats; booleans are excluded",
        ],
    }


def _case_manifest_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": sorted(_MANIFEST_FIELDS),
        "properties": {
            "case_id": _non_empty_text_schema(),
            "subject_id": _non_empty_text_schema(),
            "context": _reference_context_schema(persisted=True),
            "variants": {
                "type": "array",
                "minItems": 1,
                "maxItems": MAX_VARIANT_INTAKE_RECORDS,
                "uniqueItems": True,
                "items": _variant_identity_schema(),
                "x-uniqueBy": "variant_id",
            },
            "candidate_elements": {
                "type": "array",
                "maxItems": MAX_CASE_CANDIDATE_ELEMENTS,
                "uniqueItems": True,
                "items": _candidate_element_schema(),
                "x-uniqueBy": "element_id",
            },
            "metadata": {"type": "object"},
            "input_versions": {
                "type": "object",
                "propertyNames": {"pattern": r"\S"},
                "additionalProperties": _non_empty_text_schema(),
            },
            "requested_by": _non_empty_text_schema(),
        },
        "x-runtime-relations": [
            "variant_id values must be unique",
            "candidate element_id values must be unique",
            (
                "len(variants) * max(1, sum(1 + max(1, len(target_genes)) + "
                "max(1, len(state_ids)))) must not exceed "
                f"{MAX_CASE_RUNTIME_WORK_ITEMS}"
            ),
        ],
        "x-runtime-limits": {
            "max_targets_per_element_collection": MAX_CASE_TARGETS_PER_ELEMENT,
            "max_work_items": MAX_CASE_RUNTIME_WORK_ITEMS,
        },
    }


def _workflow_issue_schema() -> dict[str, Any]:
    fields = {
        "code",
        "severity",
        "stage",
        "message",
        "source_id",
        "line_number",
        "raw_hash",
        "remediation",
        "content_address",
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": sorted(fields),
        "properties": {
            "code": _non_empty_text_schema(),
            "severity": {"enum": [item.value for item in WorkflowSeverity]},
            "stage": {"enum": [item.value for item in WorkflowStage]},
            "message": _non_empty_text_schema(),
            "source_id": _nullable_text_schema(),
            "line_number": {"type": ["integer", "null"], "minimum": 1},
            "raw_hash": _nullable_text_schema(),
            "remediation": _non_empty_text_schema(),
            "content_address": _sha256_address_schema(),
        },
    }


def _stage_receipt_schema() -> dict[str, Any]:
    fields = {
        "stage",
        "state",
        "source_id",
        "input_address",
        "output_address",
        "observed_at",
        "record_count",
        "accepted_count",
        "rejected_count",
        "warning_count",
        "error_count",
        "issue_addresses",
        "metadata",
        "content_address",
    }
    count = {"type": "integer", "minimum": 0}
    return {
        "type": "object",
        "additionalProperties": False,
        "required": sorted(fields),
        "properties": {
            "stage": {"enum": [item.value for item in WorkflowStage]},
            "state": {"enum": [item.value for item in WorkflowState]},
            "source_id": _non_empty_text_schema(),
            "input_address": _sha256_address_schema(),
            "output_address": _sha256_address_schema(nullable=True),
            "observed_at": _non_empty_text_schema(),
            "record_count": count,
            "accepted_count": count,
            "rejected_count": count,
            "warning_count": count,
            "error_count": count,
            "issue_addresses": _text_array_schema(address_items=True),
            "metadata": {"type": "object"},
            "content_address": _sha256_address_schema(),
        },
    }


def _dossier_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": sorted(_DOSSIER_FIELDS),
        "properties": {
            "dossier_id": _non_empty_text_schema(),
            "case_id": _non_empty_text_schema(),
            "run_id": _run_id_schema(),
            "created_at": _non_empty_text_schema(),
            "input_address": _sha256_address_schema(),
            "hypotheses": {"type": "array", "items": {"type": "object"}},
            "evidence": {"type": "array", "items": {"type": "object"}},
            "experiments": {"type": "array", "items": {"type": "object"}},
            "review": {"type": ["object", "null"]},
            "research_use_only": {"type": "boolean"},
            "policy_version": _non_empty_text_schema(),
            "event_head": _sha256_address_schema(),
            "content_address": _sha256_address_schema(),
            "status": {"enum": [item.value for item in ResearchStatus]},
            "warnings": {"type": "array", "items": {"type": "string"}},
            "source_receipts": {"type": "array", "items": {"type": "object"}},
            "source_bundle_addresses": {
                "type": "array",
                "items": _sha256_address_schema(),
            },
        },
    }


def _run_record_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": sorted(_RUN_RECORD_FIELDS),
        "properties": {
            "run_id": _run_id_schema(),
            "input_address": _sha256_address_schema(),
            "event_address": _sha256_address_schema(),
            "event_history": _text_array_schema(
                min_items=1,
                max_items=MAX_RUN_HISTORY_ENTRIES,
                address_items=True,
            ),
            "dossier_address": _sha256_address_schema(),
            "dossier_history": _text_array_schema(
                min_items=1,
                max_items=MAX_RUN_HISTORY_ENTRIES,
                address_items=True,
            ),
        },
        "x-runtime-relations": [
            "event_address must occur in event_history",
            "dossier_address must occur in dossier_history",
        ],
    }


def _replay_report_schema() -> dict[str, Any]:
    fields = {
        "run_id",
        "event_chain_valid",
        "input_address",
        "dossier_address",
        "stored_dossier_matches_address",
        "warnings",
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": sorted(fields),
        "properties": {
            "run_id": _run_id_schema(),
            "event_chain_valid": {"type": "boolean"},
            "input_address": _sha256_address_schema(),
            "dossier_address": _sha256_address_schema(),
            "stored_dossier_matches_address": {"type": "boolean"},
            "warnings": _text_array_schema(),
        },
    }


def variant_source_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "urn:glio-noncode:case-workflow:variant-source:v1",
        "type": "object",
        "additionalProperties": False,
        "x-parser-limits": {
            "max_records": MAX_VARIANT_INTAKE_RECORDS,
            "max_auxiliary_lines": MAX_VARIANT_INTAKE_AUXILIARY_LINES,
        },
        "required": ["source_id", "input_format", "genome_build", "payload"],
        "properties": {
            "source_id": _non_empty_text_schema(),
            "input_format": {"enum": [item.value for item in IntakeFormat]},
            "genome_build": _non_empty_text_schema(),
            "payload": {"type": "string"},
            "payload_encoding": {"enum": ["text", "base64"], "default": "text"},
            "sample_id": _nullable_text_schema() | {"default": None},
            "include_no_call": {"type": "boolean", "default": False},
            "metadata": {"type": "object", "default": {}},
        },
    }


def regulatory_track_source_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "urn:glio-noncode:case-workflow:regulatory-track-source:v1",
        "type": "object",
        "additionalProperties": False,
        "required": ["source_id", "input_format", "genome_build", "context", "payload"],
        "properties": {
            "source_id": _non_empty_text_schema(),
            "input_format": {"enum": [item.value for item in RegulatoryTrackFormat]},
            "genome_build": _non_empty_text_schema(),
            "context": _reference_context_schema(persisted=False),
            "payload": {"type": "string"},
            "payload_encoding": {"enum": ["text", "base64"], "default": "text"},
            "metadata": {"type": "object", "default": {}},
            "target_gene_keys": {
                "type": "array",
                "minItems": 1,
                "maxItems": MAX_CASE_TARGET_GENE_KEYS,
                "uniqueItems": True,
                "default": ["gene", "gene_id", "gene_name", "target_gene"],
                "items": {
                    **_non_empty_text_schema(),
                    "maxLength": MAX_CASE_TARGET_GENE_KEY_LENGTH,
                },
            },
        },
    }


def prepare_request_schema() -> dict[str, Any]:
    """Return the canonical inline-source case preparation request schema."""

    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "urn:glio-noncode:case-workflow:prepare-request:v1",
        "title": "Case preparation request",
        "description": (
            "Canonical transport request for prepare_case. The compatibility tracks alias is "
            "intentionally excluded."
        ),
        "type": "object",
        "additionalProperties": False,
        "x-runtime-limits": {
            "max_targets_per_element_collection": MAX_CASE_TARGETS_PER_ELEMENT,
            "max_work_items": MAX_CASE_RUNTIME_WORK_ITEMS,
        },
        "required": ["case_id", "subject_id", "context", "variant_source"],
        "properties": {
            "case_id": _non_empty_text_schema(),
            "subject_id": _non_empty_text_schema(),
            "context": _reference_context_schema(persisted=False),
            "variant_source": _schema_fragment(variant_source_schema()),
            "regulatory_tracks": {
                "type": "array",
                "maxItems": MAX_CASE_REGULATORY_TRACKS,
                "default": [],
                "items": _schema_fragment(regulatory_track_source_schema()),
                "x-parser-limits": {
                    "max_records_per_track": MAX_REGULATORY_TRACK_RECORDS,
                    "max_auxiliary_lines_per_track": MAX_REGULATORY_TRACK_AUXILIARY_LINES,
                    "max_candidate_elements_per_case": MAX_CASE_CANDIDATE_ELEMENTS,
                },
            },
            "metadata": {
                "type": ["object", "null"],
                "default": None,
                "propertyNames": {
                    "not": {"const": "case_workflow_provenance"},
                },
            },
            "requested_by": _non_empty_text_schema() | {"default": "unspecified"},
            "live_reference": {"type": "boolean", "default": False},
        },
    }


def prepared_case_schema() -> dict[str, Any]:
    issue_schema = _workflow_issue_schema()
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "urn:glio-noncode:case-workflow:prepared-case:v1",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "version",
            "state",
            "accepted",
            "blocked",
            "manifest",
            "manifest_address",
            "run_id",
            "live_reference",
            "stage_receipts",
            "issues",
            "content_address",
        ],
        "properties": {
            "version": {"const": WORKFLOW_VERSION},
            "state": {"enum": [item.value for item in WorkflowState]},
            "accepted": {"type": "boolean"},
            "blocked": {"type": "boolean"},
            "manifest": {"oneOf": [_case_manifest_schema(), {"type": "null"}]},
            "manifest_address": _sha256_address_schema(nullable=True),
            "run_id": _run_id_schema(nullable=True),
            "live_reference": {"type": "boolean"},
            "stage_receipts": {"type": "array", "items": _stage_receipt_schema()},
            "issues": {"type": "array", "items": issue_schema},
            "content_address": _sha256_address_schema(),
        },
        "oneOf": [
            {
                "title": "Accepted preparation",
                "properties": {
                    "state": {"const": WorkflowState.ACCEPTED.value},
                    "accepted": {"const": True},
                    "blocked": {"const": False},
                    "manifest": {"type": "object"},
                    "manifest_address": _sha256_address_schema(),
                    "run_id": _run_id_schema(),
                    "issues": {
                        "not": {
                            "contains": {
                                "type": "object",
                                "required": ["severity"],
                                "properties": {
                                    "severity": {"const": WorkflowSeverity.ERROR.value}
                                },
                            }
                        }
                    },
                },
            },
            {
                "title": "Blocked preparation",
                "properties": {
                    "state": {"const": WorkflowState.BLOCKED.value},
                    "accepted": {"const": False},
                    "blocked": {"const": True},
                    "manifest": {"type": "null"},
                    "manifest_address": {"type": "null"},
                    "run_id": {"type": "null"},
                },
            },
        ],
        "x-runtime-relations": [
            "manifest_address must equal the canonical manifest content address",
            "run_id must equal the identifier derived from manifest identity and requested_by",
            "content_address must equal the canonical prepared-case identity address",
        ],
    }


def run_result_schema() -> dict[str, Any]:
    runtime_receipt = {
        "type": "object",
        "required": ["stage"],
        "properties": {"stage": {"const": WorkflowStage.CASE_RUNTIME.value}},
    }
    accepted_runtime_receipt = {
        "type": "object",
        "required": ["stage", "state"],
        "properties": {
            "stage": {"const": WorkflowStage.CASE_RUNTIME.value},
            "state": {"const": WorkflowState.ACCEPTED.value},
        },
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "urn:glio-noncode:case-workflow:run-result:v1",
        "type": "object",
        "additionalProperties": False,
        "x-runtime-limits": {
            "max_targets_per_element_collection": MAX_CASE_TARGETS_PER_ELEMENT,
            "max_work_items": MAX_CASE_RUNTIME_WORK_ITEMS,
            "max_run_history_items": MAX_RUN_HISTORY_ENTRIES,
        },
        "required": [
            "version",
            "state",
            "accepted",
            "blocked",
            "prepared",
            "dossier",
            "run_record",
            "replay_report",
            "stage_receipts",
            "issues",
            "content_address",
        ],
        "properties": {
            "version": {"const": WORKFLOW_VERSION},
            "state": {"enum": [item.value for item in WorkflowState]},
            "accepted": {"type": "boolean"},
            "blocked": {"type": "boolean"},
            "prepared": _schema_fragment(prepared_case_schema()),
            "dossier": {"oneOf": [_dossier_schema(), {"type": "null"}]},
            "run_record": {"oneOf": [_run_record_schema(), {"type": "null"}]},
            "replay_report": {"oneOf": [_replay_report_schema(), {"type": "null"}]},
            "stage_receipts": {"type": "array", "items": _stage_receipt_schema()},
            "issues": {"type": "array", "items": _workflow_issue_schema()},
            "content_address": _sha256_address_schema(),
        },
        "oneOf": [
            {
                "title": "Accepted execution",
                "properties": {
                    "state": {"const": WorkflowState.ACCEPTED.value},
                    "accepted": {"const": True},
                    "blocked": {"const": False},
                    "prepared": {
                        "type": "object",
                        "required": ["state", "accepted", "blocked"],
                        "properties": {
                            "state": {"const": WorkflowState.ACCEPTED.value},
                            "accepted": {"const": True},
                            "blocked": {"const": False},
                        },
                    },
                    "dossier": {"type": "object"},
                    "run_record": {"type": "object"},
                    "replay_report": {
                        "type": "object",
                        "required": [
                            "event_chain_valid",
                            "stored_dossier_matches_address",
                        ],
                        "properties": {
                            "event_chain_valid": {"const": True},
                            "stored_dossier_matches_address": {"const": True},
                        },
                    },
                    "stage_receipts": {
                        "allOf": [
                            {
                                "contains": runtime_receipt,
                                "minContains": 1,
                                "maxContains": 1,
                            },
                            {
                                "contains": accepted_runtime_receipt,
                                "minContains": 1,
                            },
                        ]
                    },
                    "issues": {
                        "not": {
                            "contains": {
                                "type": "object",
                                "required": ["severity"],
                                "properties": {
                                    "severity": {"const": WorkflowSeverity.ERROR.value}
                                },
                            }
                        }
                    },
                },
            },
            {
                "title": "Blocked execution",
                "properties": {
                    "state": {"const": WorkflowState.BLOCKED.value},
                    "accepted": {"const": False},
                    "blocked": {"const": True},
                },
            },
        ],
        "x-runtime-relations": [
            "prepared, dossier, run_record, replay_report, and runtime receipt IDs must agree",
            "all input and dossier addresses must agree across the accepted run bundle",
            "run-record current addresses must occur in their corresponding histories",
            "content_address must equal the canonical case-run-result identity address",
        ],
    }


def _rna_consequence_execution_input_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "urn:glio-noncode:case-workflow:rna-consequence-execution-input:v1",
        "title": "Optional matched-RNA execution input",
        "description": (
            "Canonical RNAConsequenceEvidence mappings accepted by run_case; Python callers "
            "may supply the corresponding typed immutable objects."
        ),
        "type": "array",
        "maxItems": MAX_CASE_RNA_CONSEQUENCES,
        "uniqueItems": True,
        "items": {
            "type": "object",
            "additionalProperties": False,
            "required": sorted(_RNA_CONSEQUENCE_REQUIRED_FIELDS),
            "properties": {
                "schema_version": {"const": EXPRESSION_EVIDENCE_SCHEMA_VERSION},
                "prediction_id": {"type": "string", "minLength": 1},
                "prediction_address": {"type": "string", "minLength": 1},
                "variant_id": {"type": "string", "minLength": 1},
                "feature_id": {"type": "string", "minLength": 1},
                "context_key": {"type": "string", "minLength": 1},
                "predicted_direction": {"enum": [item.value for item in RegulatoryDirection]},
                "state": {"enum": [item.value for item in RNAEvidenceState]},
                "expression_state": {"enum": [None, *(item.value for item in RNAEvidenceState)]},
                "expression_direction": {
                    "enum": [None, *(item.value for item in ExpressionDirection)]
                },
                "expression_robust_z": {"type": ["number", "null"]},
                "expression_result_address": {"type": ["string", "null"]},
                "allelic_state": {"enum": [None, *(item.value for item in RNAEvidenceState)]},
                "allelic_direction": {"enum": [None, *(item.value for item in AllelicDirection)]},
                "allelic_log2_ratio": {"type": ["number", "null"]},
                "allelic_q_value": {
                    "type": ["number", "null"],
                    "minimum": 0.0,
                    "maximum": 1.0,
                },
                "allelic_result_address": {"type": ["string", "null"]},
                "reason_codes": {
                    "type": "array",
                    "uniqueItems": True,
                    "items": _non_empty_text_schema(),
                },
                "content_address": {
                    "type": "string",
                    "pattern": "^rna-consequence-evidence:[0-9a-f]{64}$",
                },
            },
        },
    }


def run_request_schema() -> dict[str, Any]:
    """Return the canonical prepared-case execution request schema."""

    rna_consequences = _schema_fragment(_rna_consequence_execution_input_schema())
    rna_consequences["default"] = []
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "urn:glio-noncode:case-workflow:run-request:v1",
        "title": "Case execution request",
        "description": (
            "Canonical scientific request for run_case. Runtime and data-root selection are "
            "host configuration and are intentionally excluded."
        ),
        "type": "object",
        "additionalProperties": False,
        "x-runtime-limits": {
            "max_targets_per_element_collection": MAX_CASE_TARGETS_PER_ELEMENT,
            "max_work_items": MAX_CASE_RUNTIME_WORK_ITEMS,
        },
        "required": ["prepared"],
        "properties": {
            "prepared": _schema_fragment(prepared_case_schema()),
            "rna_consequences": rna_consequences,
        },
    }


def case_workflow_schema() -> dict[str, Any]:
    """Return the complete inline-source facade contract."""

    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "urn:glio-noncode:case-workflow:v1",
        "version": WORKFLOW_VERSION,
        "title": "Case workflow request",
        "type": "object",
        "x-runtime-limits": {
            "max_targets_per_element_collection": MAX_CASE_TARGETS_PER_ELEMENT,
            "max_work_items": MAX_CASE_RUNTIME_WORK_ITEMS,
        },
        "oneOf": [
            {"$ref": "#/$defs/prepare_request"},
            {"$ref": "#/$defs/run_request"},
        ],
        "unevaluatedProperties": False,
        "$defs": {
            "prepare_request": prepare_request_schema(),
            "run_request": run_request_schema(),
            "variant_source": variant_source_schema(),
            "regulatory_track_source": regulatory_track_source_schema(),
            "prepared_case": prepared_case_schema(),
            "run_result": run_result_schema(),
            "rna_consequence_execution_input": _rna_consequence_execution_input_schema(),
        },
    }


def capabilities() -> dict[str, Any]:
    """Describe behavior clients can rely on without exposing local configuration."""

    return {
        "version": WORKFLOW_VERSION,
        "apis": ["prepare_case", "run_case"],
        "variant_formats": [item.value for item in IntakeFormat],
        "regulatory_track_formats": [item.value for item in RegulatoryTrackFormat],
        "source_transport": ["inline_text", "inline_bytes"],
        "server_local_paths": False,
        "preparation_inputs": {
            "variant_source": {
                "max_records": MAX_VARIANT_INTAKE_RECORDS,
                "max_auxiliary_lines": MAX_VARIANT_INTAKE_AUXILIARY_LINES,
            },
            "regulatory_tracks": {
                "max_items": MAX_CASE_REGULATORY_TRACKS,
                "max_records_per_track": MAX_REGULATORY_TRACK_RECORDS,
                "max_auxiliary_lines_per_track": MAX_REGULATORY_TRACK_AUXILIARY_LINES,
                "max_candidate_elements_per_case": MAX_CASE_CANDIDATE_ELEMENTS,
                "max_target_gene_keys_per_track": MAX_CASE_TARGET_GENE_KEYS,
                "max_target_gene_key_length": MAX_CASE_TARGET_GENE_KEY_LENGTH,
                "canonical_order": "source identity and canonical content",
            },
        },
        "runtime_work_limits": {
            "max_targets_per_element_collection": MAX_CASE_TARGETS_PER_ELEMENT,
            "max_work_items": MAX_CASE_RUNTIME_WORK_ITEMS,
            "work_item_formula": (
                "variant_count * max(1, sum(1 + max(1, target_gene_count) + "
                "max(1, state_id_count)))"
            ),
            "max_run_history_items": MAX_RUN_HISTORY_ENTRIES,
        },
        "canonical_track_order": True,
        "canonical_rna_order": "RNAConsequenceEvidence.content_address",
        "observational_timestamps_in_scientific_identity": False,
        "deterministic_outputs": [
            "manifest_address",
            "run_id",
            "evaluation_run_id",
            "rna_input_address",
            "stage_receipt_address",
        ],
        "optional_execution_inputs": {
            "rna_consequences": {
                "python_inputs": ["RNAConsequenceEvidence", "strict_mapping"],
                "schema": _rna_consequence_execution_input_schema()["$id"],
                "max_items": MAX_CASE_RNA_CONSEQUENCES,
                "receipt_provenance": [
                    "rna_consequence_count",
                    "rna_consequence_addresses",
                    "rna_input_address",
                ],
                "raw_values_in_receipts": False,
            }
        },
        "identity_semantics": {
            "prepared_run_id": "manifest-only preparation identity",
            "evaluation_run_id": (
                "manifest identity plus sorted RNA consequence content addresses when non-empty"
            ),
            "empty_rna_preserves_prepared_run_id": True,
        },
        "fail_closed_gates": [
            "intake_error",
            "regulatory_track_error",
            "genome_build_mismatch",
            "duplicate_element_id",
            "no_candidate_elements_unless_live_reference",
            "case_runtime_work_limit_exceeded",
            "invalid_rna_consequence",
            "replay_integrity_error",
        ],
        "persistence": "CaseRuntime content-addressed dossier and event replay",
        "schemas": {
            "workflow": case_workflow_schema()["$id"],
            "prepare_request": prepare_request_schema()["$id"],
            "run_request": run_request_schema()["$id"],
            "variant_source": variant_source_schema()["$id"],
            "regulatory_track_source": regulatory_track_source_schema()["$id"],
            "prepared_case": prepared_case_schema()["$id"],
            "run_result": run_result_schema()["$id"],
            "rna_consequence_execution_input": _rna_consequence_execution_input_schema()["$id"],
        },
    }


# Predictable aliases for clients that use module-qualified naming.
workflow_schema = case_workflow_schema
case_workflow_capabilities = capabilities


__all__ = [
    "MAX_CASE_CANDIDATE_ELEMENTS",
    "MAX_CASE_REGULATORY_TRACKS",
    "MAX_CASE_RUNTIME_WORK_ITEMS",
    "MAX_CASE_RNA_CONSEQUENCES",
    "MAX_CASE_TARGET_GENE_KEYS",
    "MAX_CASE_TARGET_GENE_KEY_LENGTH",
    "MAX_CASE_TARGETS_PER_ELEMENT",
    "WORKFLOW_VERSION",
    "CaseRunResult",
    "PreparedCase",
    "RegulatoryTrackSource",
    "RegulatoryTrackSourceInput",
    "RunCaseResult",
    "StageReceipt",
    "VariantSource",
    "VariantSourceInput",
    "WorkflowIssue",
    "WorkflowSeverity",
    "WorkflowStage",
    "WorkflowState",
    "capabilities",
    "case_workflow_capabilities",
    "case_workflow_schema",
    "prepare_case",
    "prepare_request_schema",
    "prepared_case_schema",
    "regulatory_track_source_schema",
    "run_case",
    "run_request_schema",
    "run_result_schema",
    "variant_source_schema",
    "workflow_schema",
]
