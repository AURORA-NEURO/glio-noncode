"""Context-bound, content-addressed public atlas retrieval.

Adapter output is untrusted until its type, identity, provenance, bounds, and
content address have been checked. Source failures remain explicit abstentions;
they are never silently converted into negative biological observations.
"""

from __future__ import annotations

import hashlib
import math
import re
import threading
from collections.abc import Callable, Mapping
from dataclasses import Field, dataclass, field, fields
from datetime import datetime, timedelta
from enum import StrEnum
from types import FunctionType, MappingProxyType
from typing import Any, Protocol, cast

from . import _callback_isolation as _callback_isolation_module
from ._callback_isolation import atlas_callback_scope, detached_callback_guard
from .data_sources import (
    EncodeRestClient,
    EnsemblRestClient,
    FetchReceipt,
    FetchStatus,
    PublicReferenceRetriever,
    RateLimiter,
    ReferenceBundle,
    ReferenceRetrievalLimits,
    RetryPolicy,
    SequenceSlice,
    SourceCache,
    SourceCatalog,
    SourceClient,
    SourcePayload,
    SourceSpec,
    UcscRestClient,
    UrllibTransport,
)
from .errors import SourceError, ValidationError
from .identity import normalize_chromosome, variant_interval
from .models import (
    EvidenceClaim,
    EvidenceState,
    EvidenceTier,
    ReferenceContext,
    VariantIdentity,
    VariantKind,
    VariantOrigin,
)
from .reference_interval_index import (
    ColumnarIntervalColumns,
    IntervalBlock,
    ReferenceIndexQuery,
    ReferenceIntervalIndex,
)
from .reference_track_adapters import (
    REFERENCE_TRACK_ADAPTER_MAX_ADAPTERS,
    REFERENCE_TRACK_ADAPTER_MAX_QUERY_LIMIT,
    REFERENCE_TRACK_ADAPTER_VERSION,
    DeclaredReferenceTrackAdapter,
    ReferenceTrackAdapterRegistry,
    ReferenceTrackMetadata,
    ReferenceTrackQueryReport,
    ReferenceTrackQueryState,
    ReferenceTrackReading,
)
from .sequence_inference import (
    MotifDefinition,
    MotifHit,
    MotifScanner,
    SequenceAnalysisResult,
    SequenceAnalysisState,
    SequenceInference,
)
from .serialization import canonical_bytes, content_hash, freeze_json, jsonable
from .uncertainty import (
    DomainProfile,
    OODAssessment,
    OODStatus,
    OutOfDomainDetector,
    UncertaintyBand,
    UncertaintyComponent,
    UncertaintyPropagator,
    UncertaintyReport,
)

MAX_ATLAS_TEXT_LENGTH = 4_096
MAX_ATLAS_IDENTIFIER_LENGTH = 1_024
MAX_ATLAS_ALLELE_LENGTH = 100_000
MAX_ATLAS_CONTEXT_ASSAYS = 256
MAX_ATLAS_OBSERVATIONS = 25_000
MAX_ATLAS_RECEIPTS = 256
MAX_ATLAS_WARNINGS = 4_096
MAX_ATLAS_LIMITATIONS = 512
MAX_ATLAS_JSON_DEPTH = 64
MAX_ATLAS_JSON_NODES = 100_000
MAX_ATLAS_JSON_TEXT_CHARACTERS = 4 * 1024 * 1024
MAX_ATLAS_OBSERVATION_PAYLOAD_BYTES = 2 * 1024 * 1024
MAX_ATLAS_BUNDLE_BYTES = 256 * 1024 * 1024
MAX_ATLAS_TRACK_REPORTS = REFERENCE_TRACK_ADAPTER_MAX_ADAPTERS
MAX_ATLAS_TRACK_MATCHES = 32_000
MAX_ATLAS_TRACK_REPORT_BYTES = 8 * 1024 * 1024
MAX_ATLAS_MOTIFS = 256
MAX_ATLAS_MOTIF_PATTERN_LENGTH = 1_024
MAX_ATLAS_MOTIF_COMPARISONS = 50_000_000
MAX_ATLAS_POTENTIAL_MOTIF_HITS = 100_000
MAX_ATLAS_SEQUENCE_HITS = 100_000
MAX_ATLAS_UNCERTAINTY_COMPONENTS = 128

# Public constants are discoverability aids, not authority. Internal validation
# closes over private hard ceilings so rebinding an exported name cannot expand
# accepted work or payload sizes at runtime.
_HARD_TEXT_LENGTH = MAX_ATLAS_TEXT_LENGTH
_HARD_IDENTIFIER_LENGTH = MAX_ATLAS_IDENTIFIER_LENGTH
_HARD_ALLELE_LENGTH = MAX_ATLAS_ALLELE_LENGTH
_HARD_CONTEXT_ASSAYS = MAX_ATLAS_CONTEXT_ASSAYS
_HARD_OBSERVATIONS = MAX_ATLAS_OBSERVATIONS
_HARD_RECEIPTS = MAX_ATLAS_RECEIPTS
_HARD_WARNINGS = MAX_ATLAS_WARNINGS
_HARD_LIMITATIONS = MAX_ATLAS_LIMITATIONS
_HARD_JSON_DEPTH = MAX_ATLAS_JSON_DEPTH
_HARD_JSON_NODES = MAX_ATLAS_JSON_NODES
_HARD_JSON_TEXT_CHARACTERS = MAX_ATLAS_JSON_TEXT_CHARACTERS
_HARD_OBSERVATION_PAYLOAD_BYTES = MAX_ATLAS_OBSERVATION_PAYLOAD_BYTES
_HARD_BUNDLE_BYTES = MAX_ATLAS_BUNDLE_BYTES
_HARD_TRACK_REPORTS = MAX_ATLAS_TRACK_REPORTS
_HARD_TRACK_MATCHES = MAX_ATLAS_TRACK_MATCHES
_HARD_TRACK_REPORT_BYTES = MAX_ATLAS_TRACK_REPORT_BYTES
_HARD_MOTIFS = MAX_ATLAS_MOTIFS
_HARD_MOTIF_PATTERN_LENGTH = MAX_ATLAS_MOTIF_PATTERN_LENGTH
_HARD_MOTIF_COMPARISONS = MAX_ATLAS_MOTIF_COMPARISONS
_HARD_POTENTIAL_MOTIF_HITS = MAX_ATLAS_POTENTIAL_MOTIF_HITS
_HARD_SEQUENCE_HITS = MAX_ATLAS_SEQUENCE_HITS
_HARD_UNCERTAINTY_COMPONENTS = MAX_ATLAS_UNCERTAINTY_COMPONENTS

_SHA256_ADDRESS = re.compile(r"sha256:[0-9a-f]{64}\Z")
_CONTENT_ADDRESS = re.compile(r"[a-z][a-z0-9-]*:[0-9a-f]{64}\Z")
_ATLAS_OOD_ADDRESS_PREFIX = "atlas-ood-v1"
_ATLAS_REPLAY_INPUTS_VERSION = "atlas-replay-inputs-v1"
_SUCCESSFUL_CONTENT_STATUSES = frozenset({FetchStatus.FETCHED, FetchStatus.CACHE_HIT})
_ABSENCE_STATUSES = frozenset({FetchStatus.FETCHED, FetchStatus.CACHE_HIT, FetchStatus.NOT_FOUND})
_SUPPORTED_REFERENCE_FEATURE_TYPES = frozenset({"gene", "motif", "regulatory"})
_UNINFORMATIVE_STATES = frozenset({EvidenceState.ABSTAINED, EvidenceState.OUT_OF_DOMAIN})
_MOTIF_WORK_CEILING_WARNING = (
    "sequence inference abstained: atlas motif work ceiling exceeded"
)
_OBSERVATION_PAYLOAD_OMISSION = "omitted_over_atlas_observation_payload_ceiling"
_RLOCK_TYPE = type(threading.RLock())
_LOCK_TYPE = type(threading.Lock())


class ReferenceBundleProvider(Protocol):
    def retrieve(
        self,
        variant: VariantIdentity,
        context: ReferenceContext,
        *,
        window_bp: int | None = None,
    ) -> ReferenceBundle: ...


class EncodeProvider(Protocol):
    def search_experiments(
        self,
        *,
        assay_title: str | None = None,
        biosample_ontology_term_name: str | None = None,
        organism: str = "Homo sapiens",
        limit: int = 25,
    ) -> SourcePayload: ...


class AtlasEncodeReplayState(StrEnum):
    """How a requested ENCODE projection can be replayed without network access."""

    NOT_REQUESTED = "not_requested"
    UNCONFIGURED = "unconfigured"
    PAYLOAD = "payload"
    FAILURE = "failure"


@dataclass(frozen=True, slots=True)
class _EncodeRetrieval:
    observation: AtlasObservation
    receipt: FetchReceipt | None
    warning: str | None
    replay_state: AtlasEncodeReplayState
    replay_payload: SourcePayload | None = None
    failure_receipt: FetchReceipt | None = None
    failure_warning: str | None = None


@dataclass(slots=True)
class _JsonBudget:
    nodes: int = 0
    text_characters: int = 0


@dataclass(frozen=True, slots=True)
class _AtlasObjectConfiguration:
    """One exact mutable object shell with explicitly exempt operational fields."""

    target: object
    target_type: type[Any]
    namespace: dict[str, object]
    attributes: tuple[tuple[str, object], ...]
    operational_names: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class _AtlasFrozenConfiguration:
    """Fields of one frozen declarative object that callbacks could still rewrite."""

    target: object
    target_type: type[Any]
    attributes: tuple[tuple[str, object], ...]


@dataclass(frozen=True, slots=True)
class _AtlasMappingConfiguration:
    """Identity-preserving snapshot of one declarative mapping."""

    target: dict[Any, Any]
    items: tuple[tuple[Any, Any], ...]


@dataclass(frozen=True, slots=True)
class _AtlasSourceConfiguration:
    """Known built-in public-source configuration below an Atlas dependency."""

    objects: tuple[_AtlasObjectConfiguration, ...]
    frozen: tuple[_AtlasFrozenConfiguration, ...]
    mappings: tuple[_AtlasMappingConfiguration, ...]
    callables: tuple[_AtlasCallableConfiguration, ...] = ()


@dataclass(frozen=True, slots=True)
class _AtlasCallableConfiguration:
    """One dependency callable binding without freezing unrelated operational state."""

    target: object
    target_type: type[Any]
    namespace: dict[str, object] | None
    name: str
    had_instance_binding: bool
    instance_binding: object | None
    class_bindings: tuple[tuple[type[Any], bool, object | None], ...]


@dataclass(frozen=True, slots=True)
class _AtlasTrackConfiguration:
    """Exact built-in track graph plus its declarative mapping containers."""

    objects: tuple[_AtlasObjectConfiguration, ...]
    frozen: tuple[_AtlasFrozenConfiguration, ...]
    mappings: tuple[_AtlasMappingConfiguration, ...]


def _required_text(
    value: object,
    label: str,
    *,
    maximum: int = _HARD_TEXT_LENGTH,
    canonical: bool = True,
) -> str:
    if type(value) is not str or not value.strip():
        raise ValidationError(f"{label} must be a non-empty string")
    if len(value) > maximum:
        raise ValidationError(f"{label} exceeds the maximum length of {maximum}")
    if canonical and value != value.strip():
        raise ValidationError(f"{label} must not have surrounding whitespace")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValidationError(f"{label} must be valid UTF-8") from exc
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValidationError(f"{label} must not contain control characters")
    return value


def _optional_text(
    value: object,
    label: str,
    *,
    maximum: int = _HARD_TEXT_LENGTH,
) -> str | None:
    if value is None:
        return None
    return _required_text(value, label, maximum=maximum)


def _bounded_integer(value: object, label: str, *, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValidationError(f"{label} must be an integer between {minimum} and {maximum}")
    return value


def _bounded_float(value: object, label: str, *, minimum: float, maximum: float) -> float:
    if type(value) is not float or not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValidationError(f"{label} must be a finite float between {minimum} and {maximum}")
    return value


def _content_address(value: object, label: str, *, sha256: bool = False) -> str:
    if type(value) is not str:
        raise ValidationError(f"{label} must be a canonical content address")
    pattern = _SHA256_ADDRESS if sha256 else _CONTENT_ADDRESS
    if pattern.fullmatch(value) is None:
        raise ValidationError(f"{label} must be a canonical content address")
    return value


def _exact_object(
    value: object,
    label: str,
    fields: frozenset[str],
) -> dict[str, Any]:
    """Return an exact JSON object with one closed field set."""

    if type(value) is not dict or any(type(key) is not str for key in value):
        raise ValidationError(f"{label} must be an exact JSON object")
    if frozenset(value) != fields:
        raise ValidationError(f"{label} fields are not exact")
    return cast(dict[str, Any], value)


def _exact_array(value: object, label: str, *, maximum: int) -> list[Any]:
    """Return an exact, preflight-bounded JSON array."""

    if type(value) is not list:
        raise ValidationError(f"{label} must be an exact JSON array")
    if len(value) > maximum:
        raise ValidationError(f"{label} exceeds its hard item ceiling")
    return value


def _bounded_canonical_bytes(value: object, label: str, maximum: int) -> bytes:
    try:
        encoded = canonical_bytes(value)
    except (TypeError, ValueError, OverflowError, UnicodeError, RecursionError) as exc:
        raise ValidationError(f"{label} is not canonical JSON") from exc
    if len(encoded) > maximum:
        raise ValidationError(f"{label} exceeds its canonical byte ceiling")
    return encoded


def _utc_timestamp(value: object, label: str) -> str:
    timestamp = _required_text(value, label, maximum=128)
    try:
        parsed = datetime.fromisoformat(timestamp)
    except ValueError as exc:
        raise ValidationError(f"{label} must be a canonical UTC timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValidationError(f"{label} must be a canonical UTC timestamp")
    if parsed.isoformat() != timestamp:
        raise ValidationError(f"{label} must use datetime.isoformat() spelling")
    return timestamp


def _text_tuple(
    value: object,
    label: str,
    *,
    maximum_items: int,
    item_maximum: int = _HARD_TEXT_LENGTH,
    sort: bool = False,
) -> tuple[str, ...]:
    if type(value) is not tuple or len(value) > maximum_items:
        raise ValidationError(f"{label} must be a tuple of at most {maximum_items} strings")
    result = tuple(
        _required_text(item, f"{label}[{index}]", maximum=item_maximum)
        for index, item in enumerate(value)
    )
    if len(result) != len(set(result)):
        raise ValidationError(f"{label} must contain unique strings")
    return tuple(sorted(result)) if sort else result


def _copy_bounded_json(
    value: object,
    *,
    label: str,
    budget: _JsonBudget,
    depth: int = 0,
    active: set[int] | None = None,
) -> Any:
    if depth > _HARD_JSON_DEPTH:
        raise ValidationError(f"{label} nesting exceeds {_HARD_JSON_DEPTH}")
    budget.nodes += 1
    if budget.nodes > _HARD_JSON_NODES:
        raise ValidationError(f"{label} exceeds {_HARD_JSON_NODES} JSON nodes")
    if value is None or type(value) in {bool, int}:
        if type(value) is int and value.bit_length() > 63:
            raise ValidationError(f"{label} integers must fit in signed 64-bit range")
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise ValidationError(f"{label} numbers must be finite")
        return value
    if type(value) is str:
        budget.text_characters += len(value)
        if budget.text_characters > _HARD_JSON_TEXT_CHARACTERS:
            raise ValidationError(f"{label} exceeds {_HARD_JSON_TEXT_CHARACTERS} text characters")
        return value
    if not isinstance(value, (Mapping, list, tuple)):
        raise ValidationError(f"{label} must contain only canonical JSON values")

    seen = set() if active is None else active
    marker = id(value)
    if marker in seen:
        raise ValidationError(f"{label} must not contain recursive containers")
    seen.add(marker)
    try:
        if isinstance(value, Mapping):
            result: dict[str, Any] = {}
            try:
                for key, item in value.items():
                    if type(key) is not str:
                        raise ValidationError(f"{label} object keys must be strings")
                    _required_text(
                        key,
                        f"{label} object key",
                        maximum=_HARD_TEXT_LENGTH,
                        canonical=False,
                    )
                    budget.text_characters += len(key)
                    if budget.text_characters > _HARD_JSON_TEXT_CHARACTERS:
                        raise ValidationError(
                            f"{label} exceeds {_HARD_JSON_TEXT_CHARACTERS} text characters"
                        )
                    result[key] = _copy_bounded_json(
                        item,
                        label=f"{label}.{key}",
                        budget=budget,
                        depth=depth + 1,
                        active=seen,
                    )
            except ValidationError:
                raise
            except Exception as exc:  # noqa: BLE001 - adapter mappings are untrusted
                raise ValidationError(f"{label} could not be inspected safely") from exc
            return result
        result_array: list[Any] = []
        try:
            for index, item in enumerate(value):
                result_array.append(
                    _copy_bounded_json(
                        item,
                        label=f"{label}[{index}]",
                        budget=budget,
                        depth=depth + 1,
                        active=seen,
                    )
                )
        except ValidationError:
            raise
        except Exception as exc:  # noqa: BLE001 - adapter arrays are untrusted
            raise ValidationError(f"{label} could not be inspected safely") from exc
        return result_array
    finally:
        seen.remove(marker)


def _frozen_payload(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{label} must be an object")
    copied = _copy_bounded_json(value, label=label, budget=_JsonBudget())
    frozen = freeze_json(copied, field=label)
    if not isinstance(frozen, Mapping):  # pragma: no cover - checked above
        raise ValidationError(f"{label} must be an object")
    try:
        size = len(canonical_bytes(frozen))
    except (TypeError, ValueError, UnicodeError) as exc:
        raise ValidationError(f"{label} is not canonical JSON") from exc
    if size > _HARD_OBSERVATION_PAYLOAD_BYTES:
        raise ValidationError(f"{label} exceeds {_HARD_OBSERVATION_PAYLOAD_BYTES} canonical bytes")
    return frozen


def _project_observation_payload(
    expanded: Mapping[str, Any],
    compact_identity: Mapping[str, Any],
    *,
    artifact_kind: str,
) -> tuple[Mapping[str, Any], bool]:
    """Keep a full observation payload when it fits, otherwise retain a compact binding."""

    try:
        expanded_size = len(canonical_bytes(expanded))
    except (TypeError, ValueError, OverflowError, UnicodeError, RecursionError) as exc:
        raise ValidationError("atlas observation projection is not canonical JSON") from exc
    if expanded_size <= _HARD_OBSERVATION_PAYLOAD_BYTES:
        return expanded, False
    compact = {
        **compact_identity,
        "artifact_kind": _required_text(
            artifact_kind,
            "atlas observation artifact kind",
            maximum=128,
        ),
        "expanded_payload_canonical_bytes": expanded_size,
        "projection": _OBSERVATION_PAYLOAD_OMISSION,
    }
    _bounded_canonical_bytes(
        compact,
        "compact atlas observation projection",
        _HARD_OBSERVATION_PAYLOAD_BYTES,
    )
    return compact, True


def _projection_limitations(
    limitations: tuple[str, ...],
    message: str,
) -> tuple[str, ...]:
    """Append one deterministic projection limitation without overflowing its envelope."""

    selected = tuple(dict.fromkeys((*limitations, message)))
    if len(selected) <= _HARD_LIMITATIONS:
        return selected
    retained = tuple(item for item in selected if item != message)
    return (*retained[: _HARD_LIMITATIONS - 1], message)


def _fit_observation_limitations(
    limitations: tuple[str, ...],
    overflow_message: str,
) -> tuple[tuple[str, ...], bool]:
    """Fit upstream limitations while keeping overflow explicit and replayable."""

    selected = tuple(dict.fromkeys(limitations))
    if len(selected) <= _HARD_LIMITATIONS:
        return selected, False
    retained = tuple(item for item in selected if item != overflow_message)
    return (*retained[: _HARD_LIMITATIONS - 1], overflow_message), True


def _same_atlas_configuration_value(current: object, expected: object) -> bool:
    if current is expected:
        return True
    if type(expected) in {str, int, float, bool, tuple, frozenset, type(None)}:
        return type(current) is type(expected) and current == expected
    return False


def _capture_atlas_object_configuration(
    target: object,
    target_type: type[Any],
    names: frozenset[str],
    label: str,
    *,
    operational_names: frozenset[str] = frozenset(),
) -> _AtlasObjectConfiguration:
    if type(target) is not target_type:
        raise ValidationError(f"{label} has an invalid implementation type")
    try:
        namespace = vars(target)
    except Exception as exc:  # noqa: BLE001 - mutable dependency boundary
        raise ValidationError(f"{label} namespace is unavailable") from exc
    if type(namespace) is not dict or frozenset(namespace) != names:
        raise ValidationError(f"{label} has a non-canonical namespace")
    return _AtlasObjectConfiguration(
        target=target,
        target_type=target_type,
        namespace=namespace,
        attributes=tuple((name, namespace[name]) for name in sorted(names)),
        operational_names=operational_names,
    )


def _atlas_object_configuration_unchanged(
    state: _AtlasObjectConfiguration,
) -> bool:
    try:
        namespace = vars(state.target)
        return (
            type(state.target) is state.target_type
            and namespace is state.namespace
            and frozenset(namespace) == frozenset(name for name, _value in state.attributes)
            and all(
                (
                    _valid_atlas_operational_value(name, namespace[name])
                    if name in state.operational_names
                    else _same_atlas_configuration_value(namespace[name], expected)
                )
                for name, expected in state.attributes
            )
        )
    except Exception:  # noqa: BLE001 - callback mutation boundary
        return False


def _valid_atlas_operational_value(name: str, value: object) -> bool:
    return name == "_next_allowed" and type(value) is float and math.isfinite(value) and value >= 0


def _restore_atlas_object_configuration(state: _AtlasObjectConfiguration) -> None:
    preserved_operational: dict[str, object] = {}
    try:
        if type(state.target) is state.target_type:
            current_namespace = vars(state.target)
            for name in state.operational_names:
                value = current_namespace.get(name)
                if _valid_atlas_operational_value(name, value):
                    preserved_operational[name] = value
    except Exception:  # noqa: BLE001 - recovery falls back to the captured value
        preserved_operational = {}
    if type(state.target) is not state.target_type:
        object.__setattr__(state.target, "__class__", state.target_type)
    if vars(state.target) is not state.namespace:
        object.__setattr__(state.target, "__dict__", state.namespace)
    state.namespace.clear()
    state.namespace.update(state.attributes)
    state.namespace.update(preserved_operational)


def _capture_atlas_frozen_configuration(
    target: object,
    target_type: type[Any],
    label: str,
) -> _AtlasFrozenConfiguration:
    if type(target) is not target_type:
        raise ValidationError(f"{label} has an invalid implementation type")
    try:
        attributes = tuple(
            (item.name, getattr(target, item.name))
            for item in fields(cast(Any, target_type))
        )
        target_type(**dict(attributes))
    except ValidationError:
        raise
    except Exception as exc:  # noqa: BLE001 - forged frozen dependency
        raise ValidationError(f"{label} is malformed") from exc
    return _AtlasFrozenConfiguration(
        target=target,
        target_type=target_type,
        attributes=attributes,
    )


def _atlas_frozen_configuration_unchanged(
    state: _AtlasFrozenConfiguration,
) -> bool:
    try:
        return type(state.target) is state.target_type and all(
            _same_atlas_configuration_value(getattr(state.target, name), expected)
            for name, expected in state.attributes
        )
    except Exception:  # noqa: BLE001 - callback mutation boundary
        return False


def _restore_atlas_frozen_configuration(state: _AtlasFrozenConfiguration) -> None:
    if type(state.target) is not state.target_type:
        object.__setattr__(state.target, "__class__", state.target_type)
    for name, value in state.attributes:
        object.__setattr__(state.target, name, value)


def _capture_atlas_mapping_configuration(
    target: object,
    label: str,
) -> _AtlasMappingConfiguration:
    if type(target) is not dict:
        raise ValidationError(f"{label} must be a dictionary")
    selected = cast(dict[Any, Any], target)
    return _AtlasMappingConfiguration(target=selected, items=tuple(selected.items()))


def _atlas_mapping_configuration_unchanged(
    state: _AtlasMappingConfiguration,
) -> bool:
    try:
        current = tuple(state.target.items())
        return len(current) == len(state.items) and all(
            _same_atlas_configuration_value(current_key, expected_key)
            and _same_atlas_configuration_value(current_value, expected_value)
            for (current_key, current_value), (expected_key, expected_value) in zip(
                current,
                state.items,
                strict=True,
            )
        )
    except Exception:  # noqa: BLE001 - callback mutation boundary
        return False


def _restore_atlas_mapping_configuration(state: _AtlasMappingConfiguration) -> None:
    state.target.clear()
    state.target.update(state.items)


def _capture_atlas_callable_configuration(
    target: object,
    name: str,
    label: str,
) -> _AtlasCallableConfiguration:
    try:
        method = getattr(target, name)
    except Exception as exc:  # noqa: BLE001 - dependency binding boundary
        raise ValidationError(f"{label} callable is unavailable") from exc
    if not callable(method):
        raise ValidationError(f"{label} must be callable")
    try:
        namespace = vars(target)
    except TypeError:
        namespace = None
    except Exception as exc:  # noqa: BLE001 - dependency binding boundary
        raise ValidationError(f"{label} namespace is unavailable") from exc
    if namespace is not None and type(namespace) is not dict:
        raise ValidationError(f"{label} namespace is invalid")
    had_binding = namespace is not None and name in namespace
    instance_binding = None if namespace is None or not had_binding else namespace[name]
    class_bindings = tuple(
        (
            owner,
            name in vars(owner),
            vars(owner).get(name),
        )
        for owner in type(target).__mro__
    )
    return _AtlasCallableConfiguration(
        target=target,
        target_type=type(target),
        namespace=namespace,
        name=name,
        had_instance_binding=had_binding,
        instance_binding=instance_binding,
        class_bindings=class_bindings,
    )


def _atlas_callable_configuration_unchanged(
    state: _AtlasCallableConfiguration,
) -> bool:
    try:
        if type(state.target) is not state.target_type:
            return False
        if any(
            (state.name in vars(owner)) is not had_binding
            or (had_binding and vars(owner).get(state.name) is not binding)
            for owner, had_binding, binding in state.class_bindings
        ):
            return False
        if state.namespace is None:
            return callable(getattr(state.target, state.name))
        namespace = vars(state.target)
        if namespace is not state.namespace:
            return False
        if state.had_instance_binding:
            return (
                state.name in namespace
                and namespace[state.name] is state.instance_binding
                and callable(getattr(state.target, state.name))
            )
        return state.name not in namespace and callable(getattr(state.target, state.name))
    except Exception:  # noqa: BLE001 - callback mutation boundary
        return False


def _restore_atlas_callable_configuration(state: _AtlasCallableConfiguration) -> None:
    if type(state.target) is not state.target_type:
        object.__setattr__(state.target, "__class__", state.target_type)
    for owner, had_binding, binding in state.class_bindings:
        if had_binding:
            if vars(owner).get(state.name) is not binding:
                type.__setattr__(owner, state.name, binding)
        elif state.name in vars(owner):
            type.__delattr__(owner, state.name)
    if state.namespace is None:
        return
    if vars(state.target) is not state.namespace:
        object.__setattr__(state.target, "__dict__", state.namespace)
    if state.had_instance_binding:
        state.namespace[state.name] = state.instance_binding
    else:
        state.namespace.pop(state.name, None)


def _capture_source_client_configuration(
    client: object,
    label: str,
) -> _AtlasSourceConfiguration:
    client_state = _capture_atlas_object_configuration(
        client,
        SourceClient,
        frozenset(
            {
                "catalog",
                "transport",
                "retry_policy",
                "timeout_seconds",
                "cache_ttl_seconds",
                "user_agent",
                "cache",
                "_limiters",
            }
        ),
        label,
    )
    client_namespace = client_state.namespace
    catalog = client_namespace["catalog"]
    retry_policy = client_namespace["retry_policy"]
    cache = client_namespace["cache"]
    transport = client_namespace["transport"]
    catalog_state = _capture_atlas_object_configuration(
        catalog,
        SourceCatalog,
        frozenset({"_specs", "_lock"}),
        f"{label} catalog",
    )
    cache_state = _capture_atlas_object_configuration(
        cache,
        SourceCache,
        frozenset({"root", "_locks", "_lock"}),
        f"{label} cache",
    )
    if type(catalog_state.namespace["_lock"]) is not _RLOCK_TYPE:
        raise ValidationError(f"{label} catalog lock is invalid")
    if type(cache_state.namespace["_lock"]) is not _RLOCK_TYPE:
        raise ValidationError(f"{label} cache lock is invalid")
    specs_state = _capture_atlas_mapping_configuration(
        catalog_state.namespace["_specs"],
        f"{label} source catalog entries",
    )
    limiters_state = _capture_atlas_mapping_configuration(
        client_namespace["_limiters"],
        f"{label} source limiters",
    )
    specs = tuple(value for _key, value in specs_state.items)
    frozen_states = [
        _capture_atlas_frozen_configuration(
            retry_policy,
            RetryPolicy,
            f"{label} retry policy",
        ),
        *(
            _capture_atlas_frozen_configuration(
                spec,
                SourceSpec,
                f"{label} source specification",
            )
            for spec in specs
        ),
    ]
    spec_by_id = {
        cast(SourceSpec, spec).source_id: cast(SourceSpec, spec)
        for spec in specs
    }
    if frozenset(spec_by_id) != frozenset(key for key, _value in limiters_state.items):
        raise ValidationError(f"{label} source limiters do not match its catalog")
    limiter_states: list[_AtlasObjectConfiguration] = []
    for source_id, limiter in limiters_state.items:
        limiter_state = _capture_atlas_object_configuration(
            limiter,
            RateLimiter,
            frozenset({"interval_seconds", "_lock", "_next_allowed"}),
            f"{label} limiter {source_id}",
            operational_names=frozenset({"_next_allowed"}),
        )
        interval = limiter_state.namespace["interval_seconds"]
        next_allowed = limiter_state.namespace["_next_allowed"]
        expected_interval = 60.0 / spec_by_id[cast(str, source_id)].rate_limit_per_minute
        if (
            type(interval) is not float
            or not math.isfinite(interval)
            or interval != expected_interval
        ):
            raise ValidationError(f"{label} source limiter interval is invalid")
        if not _valid_atlas_operational_value("_next_allowed", next_allowed):
            raise ValidationError(f"{label} source limiter timing is invalid")
        if type(limiter_state.namespace["_lock"]) is not _LOCK_TYPE:
            raise ValidationError(f"{label} source limiter lock is invalid")
        limiter_states.append(limiter_state)

    transport_states: tuple[_AtlasObjectConfiguration, ...] = ()
    transport_callables: tuple[_AtlasCallableConfiguration, ...] = ()
    if type(transport) is UrllibTransport:
        transport_states = (
            _capture_atlas_object_configuration(
                transport,
                UrllibTransport,
                frozenset({"max_response_bytes"}),
                f"{label} transport",
            ),
        )
    else:
        transport_callables = (
            _capture_atlas_callable_configuration(
                transport,
                "request",
                f"{label} transport request",
            ),
        )
    return _AtlasSourceConfiguration(
        objects=(client_state, catalog_state, cache_state, *limiter_states, *transport_states),
        frozen=tuple(frozen_states),
        mappings=(specs_state, limiters_state),
        callables=transport_callables,
    )


def _capture_known_source_configuration(
    provider: object | None,
    label: str,
) -> _AtlasSourceConfiguration | None:
    wrapper_states: tuple[_AtlasObjectConfiguration, ...]
    frozen_states: tuple[_AtlasFrozenConfiguration, ...] = ()
    mapping_states: tuple[_AtlasMappingConfiguration, ...] = ()
    if type(provider) is PublicReferenceRetriever:
        provider_state = _capture_atlas_object_configuration(
            provider,
            PublicReferenceRetriever,
            frozenset({"client", "ensembl", "ucsc", "window_bp", "limits", "_lock"}),
            label,
        )
        namespace = provider_state.namespace
        client = namespace["client"]
        ensembl_state = _capture_atlas_object_configuration(
            namespace["ensembl"],
            EnsemblRestClient,
            frozenset({"client"}),
            f"{label} Ensembl client",
        )
        ucsc_state = _capture_atlas_object_configuration(
            namespace["ucsc"],
            UcscRestClient,
            frozenset({"client"}),
            f"{label} UCSC client",
        )
        if (
            ensembl_state.namespace["client"] is not client
            or ucsc_state.namespace["client"] is not client
            or type(namespace["_lock"]) is not _RLOCK_TYPE
        ):
            raise ValidationError(f"{label} client graph is invalid")
        frozen_states = (
            _capture_atlas_frozen_configuration(
                namespace["limits"],
                ReferenceRetrievalLimits,
                f"{label} limits",
            ),
        )
        mapping_states = (
            _capture_atlas_mapping_configuration(
                UcscRestClient._assemblies,
                f"{label} UCSC assemblies",
            ),
        )
        wrapper_states = (provider_state, ensembl_state, ucsc_state)
    elif type(provider) is EncodeRestClient:
        provider_state = _capture_atlas_object_configuration(
            provider,
            EncodeRestClient,
            frozenset({"client"}),
            label,
        )
        namespace = provider_state.namespace
        client = namespace["client"]
        wrapper_states = (provider_state,)
    else:
        return None
    client_state = _capture_source_client_configuration(client, f"{label} source client")
    return _AtlasSourceConfiguration(
        objects=(*wrapper_states, *client_state.objects),
        frozen=(*frozen_states, *client_state.frozen),
        mappings=(*mapping_states, *client_state.mappings),
        callables=client_state.callables,
    )


def _atlas_source_configuration_unchanged(
    state: _AtlasSourceConfiguration,
) -> bool:
    return (
        all(_atlas_object_configuration_unchanged(item) for item in state.objects)
        and all(_atlas_frozen_configuration_unchanged(item) for item in state.frozen)
        and all(_atlas_mapping_configuration_unchanged(item) for item in state.mappings)
        and all(_atlas_callable_configuration_unchanged(item) for item in state.callables)
    )


def _restore_atlas_source_configuration(state: _AtlasSourceConfiguration) -> None:
    for frozen_state in state.frozen:
        _restore_atlas_frozen_configuration(frozen_state)
    for object_state in state.objects:
        _restore_atlas_object_configuration(object_state)
    for mapping_state in state.mappings:
        _restore_atlas_mapping_configuration(mapping_state)
    for callable_state in state.callables:
        _restore_atlas_callable_configuration(callable_state)


def _capture_atlas_track_configuration(
    registry: object,
) -> _AtlasTrackConfiguration:
    registry_state = _capture_atlas_object_configuration(
        registry,
        ReferenceTrackAdapterRegistry,
        frozenset({"_adapters"}),
        "atlas track adapter registry",
    )
    registry_mapping = _capture_atlas_mapping_configuration(
        registry_state.namespace["_adapters"],
        "atlas track adapter registry entries",
    )
    frozen_states: list[_AtlasFrozenConfiguration] = []
    mapping_states = [registry_mapping]
    for adapter_id, adapter in registry_mapping.items:
        adapter_state = _capture_atlas_frozen_configuration(
            adapter,
            DeclaredReferenceTrackAdapter,
            f"atlas track adapter {adapter_id}",
        )
        adapter_values = dict(adapter_state.attributes)
        metadata_state = _capture_atlas_frozen_configuration(
            adapter_values["metadata"],
            ReferenceTrackMetadata,
            f"atlas track adapter {adapter_id} metadata",
        )
        index_state = _capture_atlas_frozen_configuration(
            adapter_values["index"],
            ReferenceIntervalIndex,
            f"atlas track adapter {adapter_id} index",
        )
        index_values = dict(index_state.attributes)
        columns_state = _capture_atlas_frozen_configuration(
            index_values["columns"],
            ColumnarIntervalColumns,
            f"atlas track adapter {adapter_id} columns",
        )
        frozen_states.extend((adapter_state, metadata_state, index_state, columns_state))
        for name in (
            "chromosome_ranges",
            "blocks",
            "context_counts",
            "track_counts",
            "source_counts",
        ):
            mapping_states.append(
                _capture_atlas_mapping_configuration(
                    index_values[name],
                    f"atlas track adapter {adapter_id} index {name}",
                )
            )
        blocks = cast(dict[Any, Any], index_values["blocks"])
        for chromosome_blocks in blocks.values():
            if type(chromosome_blocks) is not tuple:
                raise ValidationError("atlas track index blocks must be tuples")
            frozen_states.extend(
                _capture_atlas_frozen_configuration(
                    block,
                    IntervalBlock,
                    f"atlas track adapter {adapter_id} interval block",
                )
                for block in chromosome_blocks
            )
    return _AtlasTrackConfiguration(
        objects=(registry_state,),
        frozen=tuple(frozen_states),
        mappings=tuple(mapping_states),
    )


def _atlas_track_configuration_unchanged(
    state: _AtlasTrackConfiguration,
) -> bool:
    return (
        all(_atlas_object_configuration_unchanged(item) for item in state.objects)
        and all(_atlas_frozen_configuration_unchanged(item) for item in state.frozen)
        and all(_atlas_mapping_configuration_unchanged(item) for item in state.mappings)
    )


def _restore_atlas_track_configuration(state: _AtlasTrackConfiguration) -> None:
    for frozen_state in state.frozen:
        _restore_atlas_frozen_configuration(frozen_state)
    for object_state in state.objects:
        _restore_atlas_object_configuration(object_state)
    for mapping_state in state.mappings:
        _restore_atlas_mapping_configuration(mapping_state)


def _capture_atlas_semantic_guard(
    extra_classes: tuple[type[Any], ...] = (),
) -> tuple[Callable[[], bool], Callable[[], None]]:
    """Capture executable package semantics used across one callback-driven retrieval."""

    error_type = ValidationError
    atlas_namespace = globals()
    function_type = FunctionType
    field_type = Field
    field_slots = tuple(cast(Any, Field).__slots__)
    class_setattr = type.__setattr__
    class_delattr = type.__delattr__

    def descriptor_functions(values: tuple[object, ...]) -> tuple[FunctionType, ...]:
        selected: list[FunctionType] = []
        for descriptor in values:
            if type(descriptor) is function_type:
                selected.append(cast(FunctionType, descriptor))
            elif type(descriptor) in {staticmethod, classmethod}:
                selected.append(cast(Any, descriptor).__func__)
            elif type(descriptor) is property:
                selected.extend(
                    cast(FunctionType, function)
                    for function in (
                        cast(property, descriptor).fget,
                        cast(property, descriptor).fset,
                        cast(property, descriptor).fdel,
                    )
                    if function is not None
                )
        return tuple(selected)

    class_by_id: dict[int, type[Any]] = {}
    for candidate in (*tuple(atlas_namespace.values()), *extra_classes):
        if not isinstance(candidate, type):
            continue
        owner = getattr(candidate, "__module__", "")
        if type(owner) is str and (
            owner == "glio_noncode" or owner.startswith("glio_noncode.")
        ):
            class_by_id[id(candidate)] = candidate

    module_by_id: dict[int, dict[str, object]] = {id(atlas_namespace): atlas_namespace}
    while True:
        previous_shape = (len(module_by_id), len(class_by_id))
        for namespace in tuple(module_by_id.values()):
            for candidate in namespace.values():
                if not isinstance(candidate, type):
                    continue
                owner = getattr(candidate, "__module__", "")
                if type(owner) is str and (
                    owner == "glio_noncode" or owner.startswith("glio_noncode.")
                ):
                    class_by_id[id(candidate)] = candidate
            for function in descriptor_functions(tuple(namespace.values())):
                function_namespace = function.__globals__
                package = function_namespace.get("__package__")
                if type(package) is str and (
                    package == "glio_noncode" or package.startswith("glio_noncode.")
                ):
                    module_by_id[id(function_namespace)] = function_namespace
        for target in tuple(class_by_id.values()):
            for function in descriptor_functions(tuple(vars(target).values())):
                function_namespace = function.__globals__
                package = function_namespace.get("__package__")
                if type(package) is str and (
                    package == "glio_noncode" or package.startswith("glio_noncode.")
                ):
                    module_by_id[id(function_namespace)] = function_namespace
        if (len(module_by_id), len(class_by_id)) == previous_shape:
            break
    class_targets = tuple(class_by_id.values())
    module_namespaces = tuple(module_by_id.values())

    function_by_id: dict[int, FunctionType] = {}
    for namespace in module_namespaces:
        for function in descriptor_functions(tuple(namespace.values())):
            function_by_id[id(function)] = function
    for target in class_targets:
        for function in descriptor_functions(tuple(vars(target).values())):
            function_by_id[id(function)] = function

    pending_functions = list(function_by_id.values())
    function_index = 0
    while function_index < len(pending_functions):
        function = pending_functions[function_index]
        function_index += 1
        wrapped = vars(function).get("__wrapped__")
        nested_functions: list[object] = [wrapped]
        for cell in function.__closure__ or ():
            try:
                nested_functions.append(cell.cell_contents)
            except ValueError:
                continue
        for candidate in nested_functions:
            if type(candidate) is not function_type or id(candidate) in function_by_id:
                continue
            if len(function_by_id) >= 65_536:
                raise error_type("atlas callback semantic function graph exceeds limit")
            selected_function = cast(FunctionType, candidate)
            function_by_id[id(selected_function)] = selected_function
            pending_functions.append(selected_function)

    while True:
        function_graph_shape = (len(module_by_id), len(class_by_id), len(function_by_id))
        for function in tuple(function_by_id.values()):
            function_namespace = function.__globals__
            package = function_namespace.get("__package__")
            if type(package) is str and (
                package == "glio_noncode" or package.startswith("glio_noncode.")
            ):
                module_by_id[id(function_namespace)] = function_namespace
            nested_function_values: list[object] = [vars(function).get("__wrapped__")]
            for cell in function.__closure__ or ():
                try:
                    nested_function_values.append(cell.cell_contents)
                except ValueError:
                    continue
            for candidate in nested_function_values:
                if type(candidate) is not function_type or id(candidate) in function_by_id:
                    continue
                if len(function_by_id) >= 65_536:
                    raise error_type("atlas callback semantic function graph exceeds limit")
                selected_function = cast(FunctionType, candidate)
                function_by_id[id(selected_function)] = selected_function
        for namespace in tuple(module_by_id.values()):
            for candidate in namespace.values():
                if not isinstance(candidate, type):
                    continue
                owner = getattr(candidate, "__module__", "")
                if type(owner) is str and (
                    owner == "glio_noncode" or owner.startswith("glio_noncode.")
                ):
                    class_by_id[id(candidate)] = candidate
            for function in descriptor_functions(tuple(namespace.values())):
                function_by_id[id(function)] = function
        for target in tuple(class_by_id.values()):
            for function in descriptor_functions(tuple(vars(target).values())):
                function_by_id[id(function)] = function
        if (len(module_by_id), len(class_by_id), len(function_by_id)) == function_graph_shape:
            break

    class_targets = tuple(class_by_id.values())
    module_namespaces = tuple(module_by_id.values())

    function_states: list[tuple[Any, ...]] = []
    for function in function_by_id.values():
        kwdefaults = function.__kwdefaults__
        annotations = function.__annotations__
        function_dict = vars(function)
        if kwdefaults is not None and type(kwdefaults) is not dict:
            raise error_type("atlas callback semantic function kwdefaults are invalid")
        if type(annotations) is not dict:
            raise error_type("atlas callback semantic function annotations are invalid")
        closure_states: list[tuple[object, bool, object | None]] = []
        for cell in function.__closure__ or ():
            try:
                closure_states.append((cell, True, cell.cell_contents))
            except ValueError:
                closure_states.append((cell, False, None))
        function_states.append(
            (
                function,
                function.__code__,
                function.__defaults__,
                kwdefaults,
                () if kwdefaults is None else tuple(kwdefaults.items()),
                annotations,
                tuple(annotations.items()),
                function_dict,
                tuple(function_dict.items()),
                tuple(closure_states),
            )
        )

    semantic_mapping_names = {
        "glio_noncode.sequence_inference": frozenset({"_IUPAC"}),
    }
    module_states: list[tuple[Any, ...]] = []
    for namespace in module_namespaces:
        module_name = namespace.get("__name__")
        protected_names = semantic_mapping_names.get(
            cast(str, module_name),
            frozenset(),
        )
        mappings: list[tuple[dict[Any, Any], tuple[tuple[Any, Any], ...]]] = []
        for name in protected_names:
            mapping = namespace.get(name)
            if type(mapping) is not dict:
                raise error_type(
                    f"atlas callback semantic mapping is invalid: {module_name}.{name}"
                )
            mappings.append((mapping, tuple(mapping.items())))
        module_states.append(
            (
                namespace,
                tuple(namespace.items()),
                tuple(mappings),
            )
        )

    class_states: list[tuple[Any, ...]] = []
    for target in class_targets:
        attributes = tuple(vars(target).items())
        class_mappings = tuple(
            (value, tuple(value.items()))
            for _name, value in attributes
            if type(value) is dict
        )
        dataclass_fields = vars(target).get("__dataclass_fields__")
        field_states: tuple[tuple[Field[Any], tuple[tuple[str, object], ...]], ...] = ()
        if type(dataclass_fields) is dict:
            if any(type(item) is not field_type for item in dataclass_fields.values()):
                raise error_type("atlas callback dataclass field registry is invalid")
            field_states = tuple(
                (
                    item,
                    tuple((name, getattr(item, name)) for name in field_slots),
                )
                for item in dataclass_fields.values()
            )
        class_states.append((target, attributes, class_mappings, field_states))

    def same_items(
        mapping: Mapping[Any, Any],
        expected: tuple[tuple[Any, Any], ...],
    ) -> bool:
        try:
            current = tuple(mapping.items())
            return len(current) == len(expected) and all(
                current_key == expected_key and current_value is expected_value
                for (current_key, current_value), (expected_key, expected_value) in zip(
                    current,
                    expected,
                    strict=True,
                )
            )
        except Exception:  # noqa: BLE001 - mutated semantic mapping
            return False

    def function_unchanged(state: tuple[Any, ...]) -> bool:
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
            current_closure = function.__closure__ or ()
            return (
                function.__code__ is code
                and function.__defaults__ is defaults
                and function.__kwdefaults__ is kwdefaults
                and (
                    kwdefaults is None
                    or same_items(kwdefaults, kwdefault_items)
                )
                and function.__annotations__ is annotations
                and same_items(annotations, annotation_items)
                and vars(function) is function_dict
                and same_items(function_dict, function_dict_items)
                and len(current_closure) == len(closure_states)
                and all(
                    current_cell is expected_cell
                    and (
                        (had_value and current_cell.cell_contents is value)
                        or (not had_value and _cell_is_empty(current_cell))
                    )
                    for current_cell, (expected_cell, had_value, value) in zip(
                        current_closure,
                        closure_states,
                        strict=True,
                    )
                )
            )
        except Exception:  # noqa: BLE001 - mutated executable state
            return False

    def _cell_is_empty(cell: object) -> bool:
        try:
            _ = cast(Any, cell).cell_contents
        except ValueError:
            return True
        return False

    # Every helper that can execute after an untrusted callback must resolve
    # globals through an invocation-stable namespace.  Rebinding these locals
    # also makes the higher-level closures retain the detached helper chain.
    same_items = cast(Any, detached_callback_guard(same_items))
    _cell_is_empty = cast(Any, detached_callback_guard(_cell_is_empty))
    function_unchanged = cast(Any, detached_callback_guard(function_unchanged))

    def difference() -> str | None:
        try:
            for namespace, attributes, mappings in module_states:
                if not same_items(namespace, attributes):
                    expected = dict(attributes)
                    changed_names = sorted(
                        name
                        for name in set(namespace) | set(expected)
                        if name not in namespace
                        or name not in expected
                        or namespace[name] is not expected[name]
                    )
                    return (
                        f"module namespace {namespace.get('__name__', '<unknown>')}"
                        f" ({changed_names[:3]})"
                    )
                for mapping, items in mappings:
                    if not same_items(mapping, items):
                        return (
                            "semantic mapping in module "
                            f"{namespace.get('__name__', '<unknown>')}"
                        )
            for state in function_states:
                if not function_unchanged(state):
                    function = cast(FunctionType, state[0])
                    return f"function {function.__module__}.{function.__qualname__}"
            for target, attributes, mappings, field_states in class_states:
                if not same_items(vars(target), attributes):
                    return f"class namespace {target.__module__}.{target.__qualname__}"
                for mapping, items in mappings:
                    if not same_items(mapping, items):
                        return f"class mapping {target.__module__}.{target.__qualname__}"
                for item, values in field_states:
                    if any(getattr(item, name) is not value for name, value in values):
                        return f"dataclass field {target.__module__}.{target.__qualname__}"
            return None
        except Exception:  # noqa: BLE001 - mutated package semantics
            return "unreadable package semantic state"

    difference = cast(Any, detached_callback_guard(difference))

    def unchanged() -> bool:
        return difference() is None

    def restore() -> None:
        try:
            for namespace, attributes, mappings in module_states:
                expected = dict(attributes)
                for name in set(namespace) - set(expected):
                    del namespace[name]
                for name, value in attributes:
                    if name not in namespace or namespace[name] is not value:
                        namespace[name] = value
                for mapping, items in mappings:
                    mapping.clear()
                    mapping.update(dict(items))
            for target, attributes, mappings, field_states in class_states:
                expected = dict(attributes)
                for name in set(vars(target)) - set(expected):
                    class_delattr(target, name)
                for name, value in attributes:
                    if name not in vars(target) or vars(target)[name] is not value:
                        class_setattr(target, name, value)
                for mapping, items in mappings:
                    mapping.clear()
                    mapping.update(dict(items))
                for item, values in field_states:
                    for name, value in values:
                        setattr(item, name, value)
            for state in function_states:
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
                    raise error_type("atlas callback function closure could not be restored")
                for current_cell, (expected_cell, had_value, value) in zip(
                    current_closure,
                    closure_states,
                    strict=True,
                ):
                    if current_cell is not expected_cell:
                        raise error_type(
                            "atlas callback function closure could not be restored"
                        )
                    if had_value:
                        current_cell.cell_contents = value
                    else:
                        try:
                            del current_cell.cell_contents
                        except ValueError:
                            pass
        except Exception as exc:  # noqa: BLE001 - restoration must fail closed
            if isinstance(exc, error_type):
                raise
            raise error_type("atlas callback semantic state could not be restored") from exc
        remaining_difference = difference()
        if remaining_difference is not None:
            raise error_type(
                "atlas callback semantic state could not be restored: "
                f"{remaining_difference}"
            )

    return (
        cast(Callable[[], bool], detached_callback_guard(unchanged)),
        cast(Callable[[], None], detached_callback_guard(restore)),
    )


def _canonical_receipt(value: object, label: str = "atlas receipt") -> FetchReceipt:
    if type(value) is not FetchReceipt:
        raise ValidationError(f"{label} must be a FetchReceipt")
    try:
        return FetchReceipt(
            source_id=value.source_id,
            source_version=value.source_version,
            url=value.url,
            request_hash=value.request_hash,
            response_hash=value.response_hash,
            status=value.status,
            http_status=value.http_status,
            attempts=value.attempts,
            retrieved_at=value.retrieved_at,
            elapsed_seconds=value.elapsed_seconds,
            cache_expires_at=value.cache_expires_at,
            warnings=value.warnings,
            error_type=value.error_type,
            error_message=value.error_message,
        )
    except ValidationError:
        raise
    except Exception as exc:  # noqa: BLE001 - forged exact dataclass
        raise ValidationError(f"{label} is malformed") from exc


def _canonical_receipts(values: object) -> tuple[FetchReceipt, ...]:
    if type(values) is not tuple or len(values) > _HARD_RECEIPTS:
        raise ValidationError(
            f"atlas receipts must be a tuple of at most {_HARD_RECEIPTS} receipts"
        )
    by_request: dict[str, FetchReceipt] = {}
    for index, value in enumerate(values):
        receipt = _canonical_receipt(value, f"atlas receipts[{index}]")
        previous = by_request.get(receipt.request_hash)
        if previous is not None and previous != receipt:
            raise ValidationError("atlas receipts contain conflicting duplicate requests")
        by_request[receipt.request_hash] = receipt
    return tuple(sorted(by_request.values(), key=lambda item: (item.source_id, item.request_hash)))


def _safe_failure(prefix: str, error: BaseException) -> str:
    detail = type(error).__name__
    if error.args and type(error.args[0]) is str:
        candidate = " ".join(error.args[0].split())
        if candidate:
            detail = f"{detail}: {candidate}"
    return f"{prefix}: {detail}"[:_HARD_TEXT_LENGTH]


def _error_receipt(error: BaseException, expected_source: str | None = None) -> FetchReceipt | None:
    if not isinstance(error, SourceError):
        return None
    try:
        receipt = _canonical_receipt(getattr(error, "receipt", None), "source error receipt")
    except ValidationError:
        return None
    if expected_source is not None and receipt.source_id != expected_source:
        return None
    return receipt


def _canonical_context(value: object) -> ReferenceContext:
    if type(value) is not ReferenceContext:
        raise ValidationError("atlas context must be a ReferenceContext")
    try:
        key_fields = (
            value.genome_build,
            value.disease_class,
            value.age_group,
            value.cell_state,
            value.territory,
            value.treatment_phase,
        )
        normalized = tuple(
            _required_text(item, f"atlas context field {index}")
            for index, item in enumerate(key_fields)
        )
        if any("|" in item for item in normalized):
            raise ValidationError("atlas context key fields must not contain '|'")
        assays = _text_tuple(
            value.assay_support,
            "atlas context assay_support",
            maximum_items=_HARD_CONTEXT_ASSAYS,
            item_maximum=256,
        )
        source_version = _required_text(value.source_version, "atlas context source_version")
        context = ReferenceContext(
            genome_build=normalized[0],
            disease_class=normalized[1],
            age_group=normalized[2],
            cell_state=normalized[3],
            territory=normalized[4],
            treatment_phase=normalized[5],
            assay_support=assays,
            source_version=source_version,
        )
    except ValidationError:
        raise
    except Exception as exc:  # noqa: BLE001 - forged exact dataclass
        raise ValidationError("atlas context is malformed") from exc
    if len(context.key) > _HARD_TEXT_LENGTH:
        raise ValidationError("atlas context key exceeds the maximum length")
    return context


def _canonical_variant(value: object) -> VariantIdentity:
    if type(value) is not VariantIdentity:
        raise ValidationError("atlas variant must be a VariantIdentity")
    try:
        variant_id = _required_text(
            value.variant_id,
            "atlas variant_id",
            maximum=_HARD_IDENTIFIER_LENGTH,
        )
        if type(value.kind) is not VariantKind or type(value.origin) is not VariantOrigin:
            raise ValidationError("atlas variant kind and origin must use exact enums")
        chromosome = _required_text(value.chromosome, "atlas variant chromosome", maximum=256)
        start = _bounded_integer(value.start, "atlas variant start", minimum=1, maximum=2**63 - 1)
        end = _bounded_integer(value.end, "atlas variant end", minimum=start, maximum=2**63 - 1)
        reference = _required_text(
            value.reference,
            "atlas variant reference",
            maximum=_HARD_ALLELE_LENGTH,
        )
        alternate = _required_text(
            value.alternate,
            "atlas variant alternate",
            maximum=_HARD_ALLELE_LENGTH,
        )
        genome_build = _required_text(value.genome_build, "atlas variant genome_build")
        clonality = _required_text(value.clonality, "atlas variant clonality")
        sample_id = _required_text(value.sample_id, "atlas variant sample_id")
        annotations = _frozen_payload(value.annotations, "atlas variant annotations")
        return VariantIdentity(
            variant_id=variant_id,
            kind=value.kind,
            chromosome=chromosome,
            start=start,
            end=end,
            reference=reference,
            alternate=alternate,
            genome_build=genome_build,
            origin=value.origin,
            clonality=clonality,
            sample_id=sample_id,
            annotations=annotations,
        )
    except ValidationError:
        raise
    except Exception as exc:  # noqa: BLE001 - forged exact dataclass
        raise ValidationError("atlas variant is malformed") from exc


def _variant_scope_address(variant: VariantIdentity) -> str:
    # Atlas identity includes provenance and sample-scoped interpretation fields,
    # not only the genomic allele. Two otherwise identical alleles must not share
    # replay or evidence identities when their declared origin, clonality, sample,
    # or annotations differ.
    return content_hash(variant.to_dict(), prefix="atlas-variant")


def _context_scope_address(context: ReferenceContext) -> str:
    return content_hash(context.to_dict(), prefix="atlas-context")


def _bundle_created_at(receipts: tuple[FetchReceipt, ...]) -> str:
    if not receipts:
        # A bundle without a transport receipt has no honest wall-clock provenance.
        # Use a stable sentinel rather than manufacturing a retrieval time.
        return "1970-01-01T00:00:00+00:00"
    latest = max(datetime.fromisoformat(receipt.retrieved_at) for receipt in receipts)
    return latest.isoformat()


@dataclass(frozen=True, slots=True)
class AtlasQuery:
    """Bounded public-atlas request."""

    variant_id: str
    window_bp: int = 2_000
    include_encode_catalog: bool = False
    encode_assay_title: str | None = None
    encode_biosample: str | None = None
    encode_limit: int = 25

    def __post_init__(self) -> None:
        _required_text(
            self.variant_id,
            "atlas query variant_id",
            maximum=_HARD_IDENTIFIER_LENGTH,
        )
        _bounded_integer(self.window_bp, "atlas window_bp", minimum=1, maximum=5_000_000)
        if type(self.include_encode_catalog) is not bool:
            raise ValidationError("atlas include_encode_catalog must be a boolean")
        _optional_text(self.encode_assay_title, "atlas ENCODE assay title", maximum=256)
        _optional_text(self.encode_biosample, "atlas ENCODE biosample", maximum=256)
        _bounded_integer(self.encode_limit, "atlas encode_limit", minimum=1, maximum=1_000)

    def to_dict(self) -> dict[str, Any]:
        return cast(dict[str, Any], jsonable(self))

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> AtlasQuery:
        """Rehydrate one exact persisted atlas query."""

        value = _exact_object(
            raw,
            "atlas query",
            frozenset(
                {
                    "variant_id",
                    "window_bp",
                    "include_encode_catalog",
                    "encode_assay_title",
                    "encode_biosample",
                    "encode_limit",
                }
            ),
        )
        try:
            result = cls(
                variant_id=value["variant_id"],
                window_bp=value["window_bp"],
                include_encode_catalog=value["include_encode_catalog"],
                encode_assay_title=value["encode_assay_title"],
                encode_biosample=value["encode_biosample"],
                encode_limit=value["encode_limit"],
            )
            canonical = _canonical_query(result, result.variant_id)
        except ValidationError:
            raise
        except Exception as exc:  # noqa: BLE001 - persisted JSON is hostile
            raise ValidationError("atlas query is invalid") from exc
        if canonical_bytes(canonical.to_dict()) != canonical_bytes(value):
            raise ValidationError("atlas query is not an exact canonical representation")
        return canonical


def _canonical_query(value: object, variant_id: str) -> AtlasQuery:
    if type(value) is not AtlasQuery:
        raise ValidationError("atlas query must be an AtlasQuery")
    try:
        query = AtlasQuery(
            variant_id=value.variant_id,
            window_bp=value.window_bp,
            include_encode_catalog=value.include_encode_catalog,
            encode_assay_title=value.encode_assay_title,
            encode_biosample=value.encode_biosample,
            encode_limit=value.encode_limit,
        )
    except ValidationError:
        raise
    except Exception as exc:  # noqa: BLE001 - forged exact dataclass
        raise ValidationError("atlas query is malformed") from exc
    if query.variant_id != variant_id:
        raise ValidationError("atlas query variant_id does not match variant")
    return query


@dataclass(frozen=True, slots=True)
class AtlasObservation:
    """One source-scoped observation with limitations and retrieval receipt."""

    observation_id: str
    source_id: str
    feature_type: str
    state: EvidenceState
    tier: EvidenceTier
    summary: str
    payload: Mapping[str, Any]
    context_key: str
    context_score: float | None
    receipt: FetchReceipt | None
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _required_text(
            self.observation_id,
            "atlas observation_id",
            maximum=_HARD_IDENTIFIER_LENGTH,
        )
        _required_text(self.source_id, "atlas source_id", maximum=256)
        _required_text(self.feature_type, "atlas feature_type", maximum=256)
        _required_text(self.summary, "atlas summary")
        _required_text(self.context_key, "atlas context_key")
        if type(self.state) is not EvidenceState:
            raise ValidationError("atlas state must be an EvidenceState")
        if type(self.tier) is not EvidenceTier:
            raise ValidationError("atlas tier must be an EvidenceTier")
        if self.context_score is not None:
            _bounded_float(
                self.context_score,
                "atlas context_score",
                minimum=0.0,
                maximum=1.0,
            )
        if self.state in _UNINFORMATIVE_STATES and self.context_score is not None:
            raise ValidationError(
                "uninformative atlas observations cannot claim context confidence"
            )
        payload = _frozen_payload(self.payload, "atlas observation payload")
        limitations = _text_tuple(
            self.limitations,
            "atlas limitations",
            maximum_items=_HARD_LIMITATIONS,
            sort=True,
        )
        receipt = None if self.receipt is None else _canonical_receipt(self.receipt)
        if receipt is not None and receipt.source_id != self.source_id:
            raise ValidationError("atlas observation source_id does not match its receipt")
        if (
            receipt is not None
            and receipt.status in {FetchStatus.FAILED, FetchStatus.RATE_LIMITED}
            and self.state is not EvidenceState.ABSTAINED
        ):
            raise ValidationError("failed source receipts may only support abstained observations")
        if (
            receipt is not None
            and receipt.status is FetchStatus.ABSTAINED
            and self.state is not EvidenceState.ABSTAINED
        ):
            raise ValidationError("abstained source receipts may only support abstentions")
        if (
            receipt is not None
            and receipt.status is FetchStatus.NOT_FOUND
            and self.state not in {EvidenceState.ABSENT, EvidenceState.ABSTAINED}
        ):
            raise ValidationError("not-found receipts cannot support positive observations")
        object.__setattr__(self, "payload", payload)
        object.__setattr__(self, "limitations", limitations)
        object.__setattr__(self, "receipt", receipt)

    def to_dict(self) -> dict[str, Any]:
        return cast(dict[str, Any], jsonable(self))

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> AtlasObservation:
        """Rehydrate one exact persisted atlas observation and receipt."""

        value = _exact_object(
            raw,
            "atlas observation",
            frozenset(
                {
                    "observation_id",
                    "source_id",
                    "feature_type",
                    "state",
                    "tier",
                    "summary",
                    "payload",
                    "context_key",
                    "context_score",
                    "receipt",
                    "limitations",
                }
            ),
        )
        if type(value["payload"]) is not dict:
            raise ValidationError("atlas observation payload must be an exact JSON object")
        limitations = _exact_array(
            value["limitations"],
            "atlas observation limitations",
            maximum=_HARD_LIMITATIONS,
        )
        receipt_raw = value["receipt"]
        if receipt_raw is not None and type(receipt_raw) is not dict:
            raise ValidationError("atlas observation receipt must be an object or null")
        try:
            result = cls(
                observation_id=value["observation_id"],
                source_id=value["source_id"],
                feature_type=value["feature_type"],
                state=EvidenceState(value["state"]),
                tier=EvidenceTier(value["tier"]),
                summary=value["summary"],
                payload=value["payload"],
                context_key=value["context_key"],
                context_score=value["context_score"],
                receipt=(
                    None
                    if receipt_raw is None
                    else FetchReceipt.from_dict(receipt_raw)
                ),
                limitations=tuple(limitations),
            )
            canonical = _canonical_observations((result,))[0]
        except ValidationError:
            raise
        except Exception as exc:  # noqa: BLE001 - persisted JSON is hostile
            raise ValidationError("atlas observation is invalid") from exc
        if canonical_bytes(canonical.to_dict()) != canonical_bytes(value):
            raise ValidationError(
                "atlas observation is not an exact canonical representation"
            )
        return canonical


def _observation_sort_key(observation: AtlasObservation) -> tuple[str, str, str]:
    return (observation.source_id, observation.feature_type, observation.observation_id)


def _canonical_observations(value: object) -> tuple[AtlasObservation, ...]:
    if type(value) is not tuple or len(value) > _HARD_OBSERVATIONS:
        raise ValidationError(
            f"atlas observations must be a tuple of at most {_HARD_OBSERVATIONS} items"
        )
    observations: tuple[AtlasObservation, ...] = ()
    cloned: list[AtlasObservation] = []
    for item in value:
        if type(item) is not AtlasObservation:
            raise ValidationError("atlas observations must contain AtlasObservation objects")
        try:
            cloned.append(
                AtlasObservation(
                    observation_id=item.observation_id,
                    source_id=item.source_id,
                    feature_type=item.feature_type,
                    state=item.state,
                    tier=item.tier,
                    summary=item.summary,
                    payload=item.payload,
                    context_key=item.context_key,
                    context_score=item.context_score,
                    receipt=item.receipt,
                    limitations=item.limitations,
                )
            )
        except ValidationError:
            raise
        except Exception as exc:  # noqa: BLE001 - forged exact dataclass
            raise ValidationError("atlas observation is malformed") from exc
    observations = tuple(cloned)
    identifiers = tuple(item.observation_id for item in observations)
    if len(identifiers) != len(set(identifiers)):
        raise ValidationError("atlas observation identifiers must be unique")
    return tuple(sorted(observations, key=_observation_sort_key))


def _atlas_evidence_id(
    *,
    variant_address: str,
    context_address: str,
    query: AtlasQuery,
    source_bundle_address: str,
    replay_inputs_address: str,
    observation: AtlasObservation,
) -> str:
    return content_hash(
        {
            "variant_address": variant_address,
            "context_address": context_address,
            "query": query.to_dict(),
            "source_bundle_address": source_bundle_address,
            "replay_inputs_address": replay_inputs_address,
            "observation": observation.to_dict(),
        },
        prefix="atlas-evidence",
    )


def _canonical_motif_hit(value: object) -> MotifHit:
    if type(value) is not MotifHit:
        raise ValidationError("sequence analysis hits must be MotifHit objects")
    try:
        motif_id = _required_text(value.motif_id, "motif hit motif_id", maximum=256)
        name = _required_text(value.name, "motif hit name", maximum=512)
        start = _bounded_integer(value.start, "motif hit start", minimum=1, maximum=2**63 - 1)
        end = _bounded_integer(value.end, "motif hit end", minimum=start, maximum=2**63 - 1)
        strand = _required_text(value.strand, "motif hit strand", maximum=1)
        matched = _required_text(
            value.matched_sequence,
            "motif hit matched_sequence",
            maximum=_HARD_MOTIF_PATTERN_LENGTH,
        )
        source_id = _required_text(value.source_id, "motif hit source_id", maximum=256)
    except ValidationError:
        raise
    except Exception as exc:  # noqa: BLE001 - forged exact dataclass
        raise ValidationError("sequence analysis hit is malformed") from exc
    if strand not in {"+", "-"}:
        raise ValidationError("motif hit strand must be + or -")
    if len(matched) != end - start + 1 or any(base not in "ACGTN" for base in matched):
        raise ValidationError("motif hit sequence does not match its interval")
    return MotifHit(motif_id, name, start, end, strand, matched, source_id)


def _canonical_sequence_analysis(
    value: object,
    *,
    variant: VariantIdentity | None = None,
    sequence: SequenceSlice | None = None,
) -> SequenceAnalysisResult:
    if type(value) is not SequenceAnalysisResult:
        raise ValidationError("sequence inference must return SequenceAnalysisResult")
    try:
        variant_id = _required_text(value.variant_id, "sequence analysis variant_id")
        if type(value.state) is not SequenceAnalysisState:
            raise ValidationError("sequence analysis state is invalid")
        source_id = _required_text(value.source_id, "sequence analysis source_id", maximum=256)
        interval = value.reference_interval
        if type(interval) is not tuple or len(interval) != 3:
            raise ValidationError("sequence analysis reference_interval is invalid")
        chromosome = _required_text(interval[0], "sequence analysis chromosome", maximum=256)
        start = _bounded_integer(
            interval[1], "sequence analysis interval start", minimum=1, maximum=2**63 - 1
        )
        end = _bounded_integer(
            interval[2], "sequence analysis interval end", minimum=start, maximum=2**63 - 1
        )
        reference_hash = (
            None
            if value.reference_sequence_hash is None
            else _content_address(
                value.reference_sequence_hash, "reference sequence hash", sha256=True
            )
        )
        alternate_hash = (
            None
            if value.alternate_sequence_hash is None
            else _content_address(
                value.alternate_sequence_hash, "alternate sequence hash", sha256=True
            )
        )
        observed = _optional_text(
            value.reference_allele_observed,
            "sequence analysis reference allele",
            maximum=_HARD_ALLELE_LENGTH,
        )
        delta = value.alternate_length_delta
        if delta is not None:
            delta = _bounded_integer(
                delta,
                "sequence analysis alternate length delta",
                minimum=-_HARD_ALLELE_LENGTH,
                maximum=_HARD_ALLELE_LENGTH,
            )
        gc_reference = value.gc_fraction_reference
        if gc_reference is not None:
            _bounded_float(gc_reference, "reference GC fraction", minimum=0.0, maximum=1.0)
        gc_alternate = value.gc_fraction_alternate
        if gc_alternate is not None:
            _bounded_float(gc_alternate, "alternate GC fraction", minimum=0.0, maximum=1.0)
        if type(value.created_hits) is not tuple or type(value.disrupted_hits) is not tuple:
            raise ValidationError("sequence analysis hit collections must be tuples")
        if len(value.created_hits) + len(value.disrupted_hits) > _HARD_SEQUENCE_HITS:
            raise ValidationError(
                f"sequence analysis cannot exceed {_HARD_SEQUENCE_HITS} motif hits"
            )
        created = tuple(_canonical_motif_hit(item) for item in value.created_hits)
        disrupted = tuple(_canonical_motif_hit(item) for item in value.disrupted_hits)
        if created != tuple(sorted(created, key=lambda item: item.signature)):
            raise ValidationError("created motif hits must use canonical order")
        if disrupted != tuple(sorted(disrupted, key=lambda item: item.signature)):
            raise ValidationError("disrupted motif hits must use canonical order")
        if len({item.signature for item in created}) != len(created):
            raise ValidationError("created motif hits must be unique")
        if len({item.signature for item in disrupted}) != len(disrupted):
            raise ValidationError("disrupted motif hits must be unique")
        limitations = _text_tuple(
            value.limitations,
            "sequence analysis limitations",
            maximum_items=_HARD_LIMITATIONS,
        )
        supplied_address = _content_address(
            value.content_address,
            "sequence analysis content_address",
            sha256=True,
        )
    except ValidationError:
        raise
    except Exception as exc:  # noqa: BLE001 - forged exact dataclass
        raise ValidationError("sequence analysis is malformed") from exc

    if variant is not None and variant_id != variant.variant_id:
        raise ValidationError("sequence analysis variant_id does not match the atlas variant")
    if sequence is not None:
        if source_id != sequence.source_id:
            raise ValidationError("sequence analysis source does not match the sequence")
        if (chromosome, start, end) != (sequence.chromosome, sequence.start, sequence.end):
            raise ValidationError("sequence analysis interval does not match the sequence")
        if reference_hash != content_hash(sequence.sequence):
            raise ValidationError("sequence analysis reference hash does not match the sequence")
        expected_gc_reference = _sequence_gc_fraction(sequence.sequence)
        if gc_reference != expected_gc_reference:
            raise ValidationError("sequence analysis reference GC does not match the sequence")

    if value.state is SequenceAnalysisState.SUPPORTED:
        if variant is not None and sequence is not None:
            if variant.chromosome != sequence.chromosome:
                raise ValidationError("supported sequence analysis contig is inconsistent")
            offset = variant.start - sequence.start
            if offset < 0 or variant.end > sequence.end:
                raise ValidationError("supported sequence analysis is outside the sequence window")
            reference_observed = sequence.sequence[offset : offset + len(variant.reference)].upper()
            alternate_sequence = (
                sequence.sequence[:offset]
                + variant.alternate.upper()
                + sequence.sequence[offset + len(variant.reference) :]
            )
            if observed != reference_observed or reference_observed != variant.reference.upper():
                raise ValidationError(
                    "supported sequence analysis reference allele is inconsistent"
                )
            if alternate_hash != content_hash(alternate_sequence):
                raise ValidationError("sequence analysis alternate hash is inconsistent")
            if delta != len(variant.alternate) - len(variant.reference):
                raise ValidationError("sequence analysis alternate length delta is inconsistent")
            if gc_alternate != _sequence_gc_fraction(alternate_sequence):
                raise ValidationError("sequence analysis alternate GC is inconsistent")
        expected_payload = {
            "variant_id": variant_id,
            "source_id": source_id,
            "reference_interval": (chromosome, start, end),
            "reference_sequence_hash": reference_hash,
            "alternate_sequence_hash": alternate_hash,
            "created_hits": created,
            "disrupted_hits": disrupted,
            "alternate_length_delta": delta,
        }
    else:
        if (
            len(limitations) != 1
            or created
            or disrupted
            or alternate_hash is not None
            or delta is not None
            or gc_alternate is not None
        ):
            raise ValidationError("abstained sequence analysis fields are inconsistent")
        if variant is not None and sequence is not None:
            contained = (
                variant.chromosome == sequence.chromosome
                and variant.start >= sequence.start
                and variant.end <= sequence.end
            )
            offset = variant.start - sequence.start
            actual_observed = (
                sequence.sequence[offset : offset + len(variant.reference)].upper()
                if contained
                else None
            )
            if value.state is SequenceAnalysisState.OUT_OF_WINDOW and contained:
                raise ValidationError("sequence analysis falsely reports an out-of-window state")
            if value.state is SequenceAnalysisState.OUT_OF_WINDOW and observed is not None:
                raise ValidationError("out-of-window sequence analysis allele is inconsistent")
            if value.state is SequenceAnalysisState.REFERENCE_MISMATCH and (
                not contained
                or observed != actual_observed
                or actual_observed == variant.reference.upper()
            ):
                raise ValidationError("sequence analysis reference-mismatch state is inconsistent")
            if value.state is SequenceAnalysisState.ABSTAINED and (
                observed is not None and observed != actual_observed
            ):
                raise ValidationError("abstained sequence analysis allele is inconsistent")
        expected_payload = {
            "variant_id": variant_id,
            "source_id": source_id,
            "state": value.state,
            "reason": limitations[0],
            "reference_observed": observed,
        }
    if supplied_address != content_hash(expected_payload):
        raise ValidationError("sequence analysis content_address does not match its payload")
    return SequenceAnalysisResult(
        variant_id=variant_id,
        state=value.state,
        source_id=source_id,
        reference_interval=(chromosome, start, end),
        reference_sequence_hash=reference_hash,
        alternate_sequence_hash=alternate_hash,
        reference_allele_observed=observed,
        alternate_length_delta=delta,
        gc_fraction_reference=gc_reference,
        gc_fraction_alternate=gc_alternate,
        created_hits=created,
        disrupted_hits=disrupted,
        limitations=limitations,
        content_address=supplied_address,
    )


def _sequence_gc_fraction(sequence: str) -> float:
    if not sequence:
        return 0.0
    return round(sum(base in "GC" for base in sequence) / len(sequence), 6)


def _atlas_ood_payload(
    *,
    status: OODStatus,
    distance: float,
    missing_features: tuple[str, ...],
    out_of_range_features: tuple[str, ...],
    warnings: tuple[str, ...],
    profile_id: str,
) -> dict[str, Any]:
    """Return the complete retained preimage for the v1 atlas OOD address."""

    return {
        "status": status,
        "distance": distance,
        "missing_features": missing_features,
        "out_of_range_features": out_of_range_features,
        "warnings": warnings,
        "profile_id": profile_id,
    }


def _canonical_ood_assessment(
    value: object,
    *,
    verify_address: bool = True,
) -> OODAssessment:
    if type(value) is not OODAssessment or type(value.status) is not OODStatus:
        raise ValidationError("uncertainty OOD assessment is invalid")
    try:
        distance = _bounded_float(value.distance, "OOD distance", minimum=0.0, maximum=1.0)
        missing = _text_tuple(
            value.missing_features,
            "OOD missing_features",
            maximum_items=_HARD_UNCERTAINTY_COMPONENTS,
        )
        out_of_range = _text_tuple(
            value.out_of_range_features,
            "OOD out_of_range_features",
            maximum_items=_HARD_UNCERTAINTY_COMPONENTS,
        )
        warnings = _text_tuple(
            value.warnings,
            "OOD warnings",
            maximum_items=_HARD_WARNINGS,
        )
        profile_id = _required_text(value.profile_id, "OOD profile_id", maximum=256)
        supplied_address = _content_address(value.content_address, "OOD content_address")
    except ValidationError:
        raise
    except Exception as exc:  # noqa: BLE001 - forged exact dataclass
        raise ValidationError("uncertainty OOD assessment is malformed") from exc
    expected_address = content_hash(
        _atlas_ood_payload(
            status=value.status,
            distance=distance,
            missing_features=missing,
            out_of_range_features=out_of_range,
            warnings=warnings,
            profile_id=profile_id,
        ),
        prefix=_ATLAS_OOD_ADDRESS_PREFIX,
    )
    if verify_address and supplied_address != expected_address:
        raise ValidationError("OOD content_address does not match its retained fields")
    return OODAssessment(
        status=value.status,
        distance=distance,
        missing_features=missing,
        out_of_range_features=out_of_range,
        warnings=warnings,
        profile_id=profile_id,
        content_address=expected_address,
    )


def _canonical_uncertainty(value: object) -> UncertaintyReport:
    if type(value) is not UncertaintyReport:
        raise ValidationError("uncertainty propagator must return UncertaintyReport")
    try:
        overall = _bounded_float(value.overall, "uncertainty overall", minimum=0.0, maximum=1.0)
        if type(value.band) is not UncertaintyBand:
            raise ValidationError("uncertainty band is invalid")
        if (
            type(value.components) is not tuple
            or len(value.components) > _HARD_UNCERTAINTY_COMPONENTS
        ):
            raise ValidationError(
                "uncertainty components must be a tuple of at most "
                f"{_HARD_UNCERTAINTY_COMPONENTS} items"
            )
        components: list[UncertaintyComponent] = []
        for index, component in enumerate(value.components):
            if type(component) is not UncertaintyComponent:
                raise ValidationError("uncertainty components contain an invalid item")
            evidence_ids = _text_tuple(
                component.evidence_ids,
                f"uncertainty component[{index}] evidence_ids",
                maximum_items=_HARD_OBSERVATIONS,
            )
            components.append(
                UncertaintyComponent(
                    name=_required_text(component.name, "uncertainty component name", maximum=256),
                    value=_bounded_float(
                        component.value,
                        "uncertainty component value",
                        minimum=0.0,
                        maximum=1.0,
                    ),
                    rationale=_required_text(component.rationale, "uncertainty rationale"),
                    evidence_ids=evidence_ids,
                )
            )
        ood = value.ood
        if ood is not None:
            ood = _canonical_ood_assessment(ood)
        limitations = _text_tuple(
            value.limitations,
            "uncertainty limitations",
            maximum_items=_HARD_LIMITATIONS,
        )
        supplied_address = _content_address(
            value.content_address,
            "uncertainty content_address",
            sha256=True,
        )
    except ValidationError:
        raise
    except Exception as exc:  # noqa: BLE001 - forged exact dataclass
        raise ValidationError("uncertainty report is malformed") from exc
    payload = {"overall": overall, "band": value.band, "components": tuple(components), "ood": ood}
    if supplied_address != content_hash(payload):
        raise ValidationError("uncertainty content_address does not match its payload")
    return UncertaintyReport(
        overall=overall,
        band=value.band,
        components=tuple(components),
        ood=ood,
        limitations=limitations,
        content_address=supplied_address,
    )


def _canonical_domain_profile(value: object) -> DomainProfile:
    if type(value) is not DomainProfile:
        raise ValidationError("atlas domain_profile must be a DomainProfile")
    try:
        profile_id = _required_text(value.profile_id, "domain profile_id", maximum=256)
        context_key = _required_text(value.context_key, "domain context_key")
        required = _text_tuple(
            value.required_features,
            "domain required_features",
            maximum_items=_HARD_UNCERTAINTY_COMPONENTS,
            sort=True,
        )
        if not required:
            raise ValidationError("domain profile requires at least one feature")
        if not isinstance(value.feature_ranges, Mapping):
            raise ValidationError("domain feature_ranges must be an object")
        if len(value.feature_ranges) > _HARD_UNCERTAINTY_COMPONENTS:
            raise ValidationError("domain feature_ranges exceeds the atlas ceiling")
        ranges: dict[str, tuple[float, float]] = {}
        for key, bounds in value.feature_ranges.items():
            name = _required_text(key, "domain feature name", maximum=256)
            if type(bounds) is not tuple or len(bounds) != 2:
                raise ValidationError("domain feature bounds must be two-float tuples")
            minimum = _bounded_float(
                bounds[0], "domain feature minimum", minimum=-1e100, maximum=1e100
            )
            maximum = _bounded_float(
                bounds[1], "domain feature maximum", minimum=-1e100, maximum=1e100
            )
            if maximum <= minimum:
                raise ValidationError("domain feature maximum must exceed minimum")
            ranges[name] = (minimum, maximum)
        source_version = _required_text(value.source_version, "domain source_version")
        model_digest = _optional_text(value.model_digest, "domain model_digest")
        threshold = _bounded_float(
            value.watch_threshold,
            "domain watch_threshold",
            minimum=0.0000001,
            maximum=0.9999999,
        )
    except ValidationError:
        raise
    except Exception as exc:  # noqa: BLE001 - forged exact dataclass
        raise ValidationError("atlas domain_profile is malformed") from exc
    return DomainProfile(
        profile_id=profile_id,
        context_key=context_key,
        required_features=required,
        feature_ranges=MappingProxyType(dict(sorted(ranges.items()))),
        source_version=source_version,
        model_digest=model_digest,
        watch_threshold=threshold,
    )


def _canonical_motifs(value: object) -> tuple[MotifDefinition, ...]:
    if type(value) is not tuple or len(value) > _HARD_MOTIFS:
        raise ValidationError(f"atlas motifs must be a tuple of at most {_HARD_MOTIFS} items")
    motifs: list[MotifDefinition] = []
    for item in value:
        if type(item) is not MotifDefinition:
            raise ValidationError("atlas motifs must contain MotifDefinition objects")
        motif = MotifDefinition(
            motif_id=_required_text(item.motif_id, "motif_id", maximum=256),
            name=_required_text(item.name, "motif name", maximum=512),
            pattern=_required_text(
                item.pattern,
                "motif pattern",
                maximum=_HARD_MOTIF_PATTERN_LENGTH,
            ),
            source_id=_required_text(item.source_id, "motif source_id", maximum=256),
        )
        motifs.append(motif)
    identifiers = tuple(item.motif_id for item in motifs)
    if len(identifiers) != len(set(identifiers)):
        raise ValidationError("atlas motif identifiers must be unique")
    return tuple(sorted(motifs, key=lambda item: (item.motif_id, item.pattern, item.source_id)))


def _canonical_reference_bundle(
    value: object,
    *,
    variant: VariantIdentity,
    context: ReferenceContext,
    window_bp: int,
) -> ReferenceBundle:
    if type(value) is not ReferenceBundle:
        raise ValidationError("reference retriever must return a ReferenceBundle")
    try:
        if value.variant_id != variant.variant_id:
            raise ValidationError("reference bundle variant_id does not match the atlas variant")
        if value.context_key != context.key:
            raise ValidationError("reference bundle context does not match the atlas context")
        sorted_receipts = _canonical_receipts(value.receipts)
        receipt_by_request = {item.request_hash: item for item in sorted_receipts}
        ordered_receipts = tuple(receipt_by_request[item.request_hash] for item in value.receipts)
        sequence = value.sequence
        canonical_sequence = None
        expected_chromosome, variant_start, variant_end = variant_interval(variant)
        expected_chromosome = normalize_chromosome(expected_chromosome)
        query_start = max(1, variant_start - window_bp)
        query_end = variant_end + window_bp
        if sequence is not None:
            if type(sequence) is not SequenceSlice:
                raise ValidationError("reference bundle sequence is invalid")
            sequence_receipt = receipt_by_request.get(sequence.receipt.request_hash)
            if sequence_receipt is None or sequence_receipt != _canonical_receipt(sequence.receipt):
                raise ValidationError("reference sequence receipt is not retained by the bundle")
            canonical_sequence = SequenceSlice(
                assembly=sequence.assembly,
                chromosome=sequence.chromosome,
                start=sequence.start,
                end=sequence.end,
                sequence=sequence.sequence,
                source_id=sequence.source_id,
                receipt=sequence_receipt,
            )
            if canonical_sequence.assembly != variant.genome_build:
                raise ValidationError("reference sequence assembly does not match the variant")
            if canonical_sequence.chromosome != expected_chromosome:
                raise ValidationError("reference sequence chromosome does not match the variant")
            if canonical_sequence.start > variant_start or canonical_sequence.end < variant_end:
                raise ValidationError("reference sequence does not cover the requested variant")
            if canonical_sequence.start < query_start or canonical_sequence.end > query_end:
                raise ValidationError("reference sequence escaped the requested atlas window")
        for element in value.elements:
            if _context_scope_address(element.context) != _context_scope_address(context):
                raise ValidationError("reference element context does not exactly match the atlas")
            if normalize_chromosome(element.chromosome) != expected_chromosome:
                raise ValidationError("reference element chromosome does not match the variant")
            if element.end < query_start or element.start > query_end:
                raise ValidationError(
                    "reference element does not overlap the requested atlas window"
                )
        materialization_abstained = any(
            warning.casefold().startswith("candidate materialization abstained")
            for warning in value.warnings
        )
        for feature in value.raw_features:
            if materialization_abstained:
                # Preserve source-returned annotations as opaque, receipt-bound audit
                # evidence when promotion to typed candidates failed validation.
                continue
            feature_source = feature.get("source_id")
            if feature_source is not None and feature_source != "SRC-ENSEMBL-REST":
                raise ValidationError("reference feature source does not match Ensembl")
            feature_build = feature.get("assembly", feature.get("genome_build"))
            if feature_build is not None and feature_build != context.genome_build:
                raise ValidationError("reference feature assembly does not match the atlas")
            feature_chromosome = feature.get(
                "seq_region_name",
                feature.get("chromosome", feature.get("chrom")),
            )
            if feature_chromosome is not None and (
                type(feature_chromosome) is not str
                or normalize_chromosome(feature_chromosome) != expected_chromosome
            ):
                raise ValidationError("reference feature chromosome does not match the variant")
            feature_start = feature.get("start")
            feature_end = feature.get("end")
            if (feature_start is None) != (feature_end is None):
                raise ValidationError("reference feature coordinates must be supplied together")
            if feature_start is not None and (
                type(feature_start) is not int
                or type(feature_end) is not int
                or feature_start < 1
                or feature_end < feature_start
                or feature_end < query_start
                or feature_start > query_end
            ):
                raise ValidationError("reference feature does not overlap the atlas window")
        candidate = ReferenceBundle.create(
            variant_id=value.variant_id,
            context=context,
            sequence=canonical_sequence,
            elements=value.elements,
            raw_features=value.raw_features,
            receipts=ordered_receipts,
            warnings=value.warnings,
        )
        if candidate.content_address != value.content_address:
            raise ValidationError("reference bundle content_address does not match its payload")
        return candidate
    except ValidationError:
        raise
    except Exception as exc:  # noqa: BLE001 - forged exact dataclass or adapter object
        raise ValidationError("reference bundle is malformed") from exc


def _canonical_track_reading(
    value: object,
    *,
    metadata: ReferenceTrackMetadata,
    query: ReferenceIndexQuery,
) -> ReferenceTrackReading:
    if type(value) is not ReferenceTrackReading:
        raise ValidationError("track report matches must contain ReferenceTrackReading objects")
    try:
        adapter_id = _required_text(value.adapter_id, "track reading adapter_id", maximum=256)
        source_id = _required_text(value.source_id, "track reading source_id", maximum=256)
        source_version = _required_text(value.source_version, "track reading source_version")
        track_type = _required_text(value.track_type, "track reading track_type", maximum=256)
        record_id = _required_text(value.record_id, "track reading record_id")
        chromosome = _required_text(value.chromosome, "track reading chromosome", maximum=256)
        start = _bounded_integer(value.start, "track reading start", minimum=1, maximum=2**63 - 1)
        end = _bounded_integer(value.end, "track reading end", minimum=start, maximum=2**63 - 1)
        context_key = _required_text(value.context_key, "track reading context_key")
        state = _required_text(value.state, "track reading state", maximum=256)
        payload = _frozen_payload(value.payload, "track reading payload")
        tags = _text_tuple(value.tags, "track reading tags", maximum_items=_HARD_LIMITATIONS)
        raw_hash = _content_address(value.raw_hash, "track reading raw_hash")
        overlap_bp = _bounded_integer(
            value.overlap_bp,
            "track reading overlap_bp",
            minimum=1,
            maximum=2**63 - 1,
        )
        score = _bounded_float(
            value.context_score,
            "track reading context_score",
            minimum=0.0,
            maximum=1.0,
        )
        specificity = _bounded_integer(
            value.specificity,
            "track reading specificity",
            minimum=0,
            maximum=6,
        )
        generalized = _text_tuple(
            value.generalized_dimensions,
            "track reading generalized_dimensions",
            maximum_items=6,
        )
        supplied_address = _content_address(value.content_address, "track reading content_address")
    except ValidationError:
        raise
    except Exception as exc:  # noqa: BLE001 - forged exact dataclass
        raise ValidationError("track reading is malformed") from exc
    if (adapter_id, source_id, source_version, track_type) != (
        metadata.adapter_id,
        metadata.source_id,
        metadata.source_version,
        metadata.track_type,
    ):
        raise ValidationError("track reading identity does not match adapter metadata")
    if chromosome != query.chromosome or end < query.start or start > query.end:
        raise ValidationError("track reading does not overlap the atlas query")
    clone = ReferenceTrackReading(
        adapter_id=adapter_id,
        source_id=source_id,
        source_version=source_version,
        track_type=track_type,
        record_id=record_id,
        chromosome=chromosome,
        start=start,
        end=end,
        context_key=context_key,
        state=state,
        payload=payload,
        tags=tags,
        raw_hash=raw_hash,
        overlap_bp=overlap_bp,
        context_score=score,
        specificity=specificity,
        generalized_dimensions=generalized,
        content_address=supplied_address,
    )
    object.__setattr__(clone, "payload", payload)
    return clone


def _canonical_track_report(
    value: object,
    *,
    expected_query: ReferenceIndexQuery | None = None,
) -> ReferenceTrackQueryReport:
    if type(value) is not ReferenceTrackQueryReport:
        raise ValidationError("track adapter must return ReferenceTrackQueryReport objects")
    try:
        adapter_id = _required_text(value.adapter_id, "track report adapter_id", maximum=256)
        if type(value.metadata) is not ReferenceTrackMetadata:
            raise ValidationError("track report metadata is invalid")
        metadata = ReferenceTrackMetadata.from_dict(value.metadata.to_dict())
        metadata_address = _content_address(value.metadata_address, "track report metadata_address")
        if metadata_address != metadata.content_address:
            raise ValidationError("track report metadata_address does not match metadata")
        artifact_id = _required_text(value.artifact_id, "track report artifact_id")
        if adapter_id != metadata.adapter_id or artifact_id != metadata.artifact_id:
            raise ValidationError("track report identity does not match metadata")
        if type(value.query) is not ReferenceIndexQuery:
            raise ValidationError("track report query is invalid")
        query = ReferenceIndexQuery.from_mapping(value.query.to_dict())
        if canonical_bytes(query.to_dict()) != canonical_bytes(value.query.to_dict()):
            raise ValidationError("track report query is not canonical")
        if expected_query is not None and query != expected_query:
            raise ValidationError("track report query does not match the atlas query")
        if type(value.state) is not ReferenceTrackQueryState:
            raise ValidationError("track report state is invalid")
        if (
            type(value.matches) is not tuple
            or len(value.matches) > REFERENCE_TRACK_ADAPTER_MAX_QUERY_LIMIT
        ):
            raise ValidationError("track report matches exceed the adapter query ceiling")
        matches = tuple(
            _canonical_track_reading(item, metadata=metadata, query=query) for item in value.matches
        )
        counts = tuple(
            _bounded_integer(item, label, minimum=0, maximum=1_000_000)
            for item, label in (
                (value.interval_candidate_count, "track interval_candidate_count"),
                (value.rows_scanned, "track rows_scanned"),
                (value.context_rejected_count, "track context_rejected_count"),
                (value.filter_rejected_count, "track filter_rejected_count"),
                (value.total_match_count, "track total_match_count"),
            )
        )
        offset = _bounded_integer(value.offset, "track offset", minimum=0, maximum=1_000_000)
        limit = _bounded_integer(
            value.limit,
            "track limit",
            minimum=1,
            maximum=REFERENCE_TRACK_ADAPTER_MAX_QUERY_LIMIT,
        )
        if type(value.truncated) is not bool:
            raise ValidationError("track truncated must be a boolean")
        warnings = _text_tuple(
            value.warnings,
            "track report warnings",
            maximum_items=_HARD_WARNINGS,
        )
        supplied_address = _content_address(value.content_address, "track report content_address")
    except ValidationError:
        raise
    except Exception as exc:  # noqa: BLE001 - forged exact dataclass
        raise ValidationError("track report is malformed") from exc
    interval_count, rows_scanned, context_rejected, filter_rejected, total_matches = counts
    if rows_scanned != interval_count:
        raise ValidationError("track report row accounting is inconsistent")
    if context_rejected + filter_rejected + total_matches > rows_scanned:
        raise ValidationError("track report rejection accounting is inconsistent")
    if len(matches) > limit or total_matches < len(matches):
        raise ValidationError("track report match accounting is inconsistent")
    if offset != query.offset or limit != query.limit:
        raise ValidationError("track report paging does not match its query")
    if value.state is ReferenceTrackQueryState.TRUNCATED and not value.truncated:
        raise ValidationError("truncated track state requires truncated=true")
    if value.truncated and value.state is not ReferenceTrackQueryState.TRUNCATED:
        raise ValidationError("truncated track result must use the truncated state")
    if (
        value.state
        in {
            ReferenceTrackQueryState.ABSENT,
            ReferenceTrackQueryState.OUT_OF_DOMAIN,
            ReferenceTrackQueryState.ABSTAINED,
            ReferenceTrackQueryState.INVALID,
        }
        and matches
    ):
        raise ValidationError("non-supported track states must not retain matches")
    body = {
        "version": REFERENCE_TRACK_ADAPTER_VERSION,
        "adapter_id": adapter_id,
        "metadata_address": metadata_address,
        "artifact_id": artifact_id,
        "query": query,
        "state": value.state,
        "matches": matches,
        "interval_candidate_count": interval_count,
        "rows_scanned": rows_scanned,
        "context_rejected_count": context_rejected,
        "filter_rejected_count": filter_rejected,
        "total_match_count": total_matches,
        "offset": offset,
        "limit": limit,
        "truncated": value.truncated,
        "warnings": warnings,
    }
    if supplied_address != content_hash(body, prefix="reference-track-query"):
        raise ValidationError("track report content_address does not match its payload")
    clone = ReferenceTrackQueryReport(
        adapter_id=adapter_id,
        metadata=metadata,
        metadata_address=metadata_address,
        artifact_id=artifact_id,
        query=query,
        state=value.state,
        matches=matches,
        interval_candidate_count=interval_count,
        rows_scanned=rows_scanned,
        context_rejected_count=context_rejected,
        filter_rejected_count=filter_rejected,
        total_match_count=total_matches,
        offset=offset,
        limit=limit,
        truncated=value.truncated,
        warnings=warnings,
        content_address=supplied_address,
    )
    if len(canonical_bytes(clone.to_dict())) > _HARD_TRACK_REPORT_BYTES:
        raise ValidationError("track report exceeds the atlas canonical byte ceiling")
    return clone


def _canonical_track_report_tuple(value: object) -> tuple[ReferenceTrackQueryReport, ...]:
    if type(value) is not tuple or len(value) > _HARD_TRACK_REPORTS:
        raise ValidationError(
            f"atlas track_reports must be a tuple of at most {_HARD_TRACK_REPORTS} items"
        )
    reports = tuple(_canonical_track_report(item) for item in value)
    identifiers = tuple(item.adapter_id for item in reports)
    if len(identifiers) != len(set(identifiers)):
        raise ValidationError("atlas track adapter identifiers must be unique")
    if sum(len(item.matches) for item in reports) > _HARD_TRACK_MATCHES:
        raise ValidationError(f"atlas track matches cannot exceed {_HARD_TRACK_MATCHES}")
    return tuple(sorted(reports, key=lambda item: item.adapter_id))


def _motif_hit_from_dict(raw: Mapping[str, Any]) -> MotifHit:
    value = _exact_object(
        raw,
        "persisted motif hit",
        frozenset(
            {
                "motif_id",
                "name",
                "start",
                "end",
                "strand",
                "matched_sequence",
                "source_id",
            }
        ),
    )
    try:
        result = _canonical_motif_hit(
            MotifHit(
                motif_id=value["motif_id"],
                name=value["name"],
                start=value["start"],
                end=value["end"],
                strand=value["strand"],
                matched_sequence=value["matched_sequence"],
                source_id=value["source_id"],
            )
        )
    except ValidationError:
        raise
    except Exception as exc:  # noqa: BLE001 - persisted JSON is hostile
        raise ValidationError("persisted motif hit is invalid") from exc
    if canonical_bytes(result.to_dict()) != canonical_bytes(value):
        raise ValidationError("persisted motif hit is not an exact canonical representation")
    return result


def _sequence_analysis_from_dict(
    raw: Mapping[str, Any],
    *,
    variant: VariantIdentity,
    sequence: SequenceSlice,
) -> SequenceAnalysisResult:
    value = _exact_object(
        raw,
        "persisted sequence analysis",
        frozenset(
            {
                "variant_id",
                "state",
                "source_id",
                "reference_interval",
                "reference_sequence_hash",
                "alternate_sequence_hash",
                "reference_allele_observed",
                "alternate_length_delta",
                "gc_fraction_reference",
                "gc_fraction_alternate",
                "created_hits",
                "disrupted_hits",
                "limitations",
                "content_address",
            }
        ),
    )
    interval = _exact_array(
        value["reference_interval"],
        "persisted sequence analysis reference_interval",
        maximum=3,
    )
    if len(interval) != 3:
        raise ValidationError("persisted sequence analysis reference_interval is invalid")
    created_raw = _exact_array(
        value["created_hits"],
        "persisted sequence analysis created_hits",
        maximum=_HARD_SEQUENCE_HITS,
    )
    disrupted_raw = _exact_array(
        value["disrupted_hits"],
        "persisted sequence analysis disrupted_hits",
        maximum=_HARD_SEQUENCE_HITS,
    )
    if len(created_raw) + len(disrupted_raw) > _HARD_SEQUENCE_HITS:
        raise ValidationError("persisted sequence analysis exceeds its motif-hit ceiling")
    limitations = _exact_array(
        value["limitations"],
        "persisted sequence analysis limitations",
        maximum=_HARD_LIMITATIONS,
    )
    if any(type(item) is not dict for item in (*created_raw, *disrupted_raw)):
        raise ValidationError("persisted sequence analysis hits must be exact JSON objects")
    try:
        result = SequenceAnalysisResult(
            variant_id=value["variant_id"],
            state=SequenceAnalysisState(value["state"]),
            source_id=value["source_id"],
            reference_interval=(interval[0], interval[1], interval[2]),
            reference_sequence_hash=value["reference_sequence_hash"],
            alternate_sequence_hash=value["alternate_sequence_hash"],
            reference_allele_observed=value["reference_allele_observed"],
            alternate_length_delta=value["alternate_length_delta"],
            gc_fraction_reference=value["gc_fraction_reference"],
            gc_fraction_alternate=value["gc_fraction_alternate"],
            created_hits=tuple(_motif_hit_from_dict(item) for item in created_raw),
            disrupted_hits=tuple(_motif_hit_from_dict(item) for item in disrupted_raw),
            limitations=tuple(limitations),
            content_address=value["content_address"],
        )
        canonical = _canonical_sequence_analysis(
            result,
            variant=variant,
            sequence=sequence,
        )
    except ValidationError:
        raise
    except Exception as exc:  # noqa: BLE001 - persisted JSON is hostile
        raise ValidationError("persisted sequence analysis is invalid") from exc
    if canonical_bytes(canonical.to_dict()) != canonical_bytes(value):
        raise ValidationError(
            "persisted sequence analysis is not an exact canonical representation"
        )
    return canonical


def _ood_assessment_from_dict(raw: Mapping[str, Any]) -> OODAssessment:
    value = _exact_object(
        raw,
        "persisted OOD assessment",
        frozenset(
            {
                "status",
                "distance",
                "missing_features",
                "out_of_range_features",
                "warnings",
                "profile_id",
                "content_address",
            }
        ),
    )
    missing = _exact_array(
        value["missing_features"],
        "persisted OOD missing_features",
        maximum=_HARD_UNCERTAINTY_COMPONENTS,
    )
    out_of_range = _exact_array(
        value["out_of_range_features"],
        "persisted OOD out_of_range_features",
        maximum=_HARD_UNCERTAINTY_COMPONENTS,
    )
    warnings = _exact_array(
        value["warnings"],
        "persisted OOD warnings",
        maximum=_HARD_WARNINGS,
    )
    try:
        result = _canonical_ood_assessment(
            OODAssessment(
                status=OODStatus(value["status"]),
                distance=value["distance"],
                missing_features=tuple(missing),
                out_of_range_features=tuple(out_of_range),
                warnings=tuple(warnings),
                profile_id=value["profile_id"],
                content_address=value["content_address"],
            )
        )
    except ValidationError:
        raise
    except Exception as exc:  # noqa: BLE001 - persisted JSON is hostile
        raise ValidationError("persisted OOD assessment is invalid") from exc
    if canonical_bytes(result.to_dict()) != canonical_bytes(value):
        raise ValidationError(
            "persisted OOD assessment is not an exact canonical representation"
        )
    return result


def _uncertainty_component_from_dict(raw: Mapping[str, Any]) -> UncertaintyComponent:
    value = _exact_object(
        raw,
        "persisted uncertainty component",
        frozenset({"name", "value", "rationale", "evidence_ids"}),
    )
    evidence_ids = _exact_array(
        value["evidence_ids"],
        "persisted uncertainty component evidence_ids",
        maximum=_HARD_OBSERVATIONS,
    )
    try:
        return UncertaintyComponent(
            name=value["name"],
            value=value["value"],
            rationale=value["rationale"],
            evidence_ids=tuple(evidence_ids),
        )
    except Exception as exc:  # noqa: BLE001 - validation is completed by the report validator
        raise ValidationError("persisted uncertainty component is invalid") from exc


def _uncertainty_from_dict(raw: Mapping[str, Any]) -> UncertaintyReport:
    value = _exact_object(
        raw,
        "persisted uncertainty report",
        frozenset(
            {
                "overall",
                "band",
                "components",
                "ood",
                "limitations",
                "content_address",
            }
        ),
    )
    components_raw = _exact_array(
        value["components"],
        "persisted uncertainty components",
        maximum=_HARD_UNCERTAINTY_COMPONENTS,
    )
    limitations = _exact_array(
        value["limitations"],
        "persisted uncertainty limitations",
        maximum=_HARD_LIMITATIONS,
    )
    if any(type(item) is not dict for item in components_raw):
        raise ValidationError("persisted uncertainty components must be exact JSON objects")
    ood_raw = value["ood"]
    if ood_raw is not None and type(ood_raw) is not dict:
        raise ValidationError("persisted uncertainty OOD assessment must be an object or null")
    try:
        result = UncertaintyReport(
            overall=value["overall"],
            band=UncertaintyBand(value["band"]),
            components=tuple(
                _uncertainty_component_from_dict(item) for item in components_raw
            ),
            ood=None if ood_raw is None else _ood_assessment_from_dict(ood_raw),
            limitations=tuple(limitations),
            content_address=value["content_address"],
        )
        canonical = _canonical_uncertainty(result)
    except ValidationError:
        raise
    except Exception as exc:  # noqa: BLE001 - persisted JSON is hostile
        raise ValidationError("persisted uncertainty report is invalid") from exc
    if canonical_bytes(canonical.to_dict()) != canonical_bytes(value):
        raise ValidationError(
            "persisted uncertainty report is not an exact canonical representation"
        )
    return canonical


def _track_reading_from_dict(
    raw: Mapping[str, Any],
    *,
    metadata: ReferenceTrackMetadata,
    query: ReferenceIndexQuery,
) -> ReferenceTrackReading:
    value = _exact_object(
        raw,
        "persisted track reading",
        frozenset(
            {
                "adapter_id",
                "source_id",
                "source_version",
                "track_type",
                "record_id",
                "chromosome",
                "start",
                "end",
                "context_key",
                "state",
                "payload",
                "tags",
                "raw_hash",
                "overlap_bp",
                "context_score",
                "specificity",
                "generalized_dimensions",
                "content_address",
            }
        ),
    )
    if type(value["payload"]) is not dict:
        raise ValidationError("persisted track reading payload must be an exact JSON object")
    tags = _exact_array(
        value["tags"],
        "persisted track reading tags",
        maximum=_HARD_LIMITATIONS,
    )
    generalized = _exact_array(
        value["generalized_dimensions"],
        "persisted track reading generalized_dimensions",
        maximum=6,
    )
    try:
        result = ReferenceTrackReading(
            adapter_id=value["adapter_id"],
            source_id=value["source_id"],
            source_version=value["source_version"],
            track_type=value["track_type"],
            record_id=value["record_id"],
            chromosome=value["chromosome"],
            start=value["start"],
            end=value["end"],
            context_key=value["context_key"],
            state=value["state"],
            payload=value["payload"],
            tags=tuple(tags),
            raw_hash=value["raw_hash"],
            overlap_bp=value["overlap_bp"],
            context_score=value["context_score"],
            specificity=value["specificity"],
            generalized_dimensions=tuple(generalized),
            content_address=value["content_address"],
        )
        canonical = _canonical_track_reading(result, metadata=metadata, query=query)
    except ValidationError:
        raise
    except Exception as exc:  # noqa: BLE001 - persisted JSON is hostile
        raise ValidationError("persisted track reading is invalid") from exc
    if canonical_bytes(canonical.to_dict()) != canonical_bytes(value):
        raise ValidationError(
            "persisted track reading is not an exact canonical representation"
        )
    return canonical


def _track_report_from_dict(
    raw: Mapping[str, Any],
    *,
    expected_query: ReferenceIndexQuery,
) -> ReferenceTrackQueryReport:
    value = _exact_object(
        raw,
        "persisted track report",
        frozenset(
            {
                "version",
                "adapter_id",
                "metadata",
                "metadata_address",
                "artifact_id",
                "query",
                "state",
                "matches",
                "interval_candidate_count",
                "rows_scanned",
                "context_rejected_count",
                "filter_rejected_count",
                "total_match_count",
                "offset",
                "limit",
                "truncated",
                "warnings",
                "content_address",
                "accepted",
            }
        ),
    )
    _bounded_canonical_bytes(value, "persisted track report", _HARD_TRACK_REPORT_BYTES)
    metadata_raw = value["metadata"]
    query_raw = value["query"]
    if type(metadata_raw) is not dict or type(query_raw) is not dict:
        raise ValidationError("persisted track report metadata and query must be objects")
    matches_raw = _exact_array(
        value["matches"],
        "persisted track report matches",
        maximum=REFERENCE_TRACK_ADAPTER_MAX_QUERY_LIMIT,
    )
    warnings = _exact_array(
        value["warnings"],
        "persisted track report warnings",
        maximum=_HARD_WARNINGS,
    )
    if any(type(item) is not dict for item in matches_raw):
        raise ValidationError("persisted track report matches must be exact JSON objects")
    try:
        metadata = ReferenceTrackMetadata.from_dict(metadata_raw)
        query = ReferenceIndexQuery.from_mapping(query_raw)
        result = ReferenceTrackQueryReport(
            adapter_id=value["adapter_id"],
            metadata=metadata,
            metadata_address=value["metadata_address"],
            artifact_id=value["artifact_id"],
            query=query,
            state=ReferenceTrackQueryState(value["state"]),
            matches=tuple(
                _track_reading_from_dict(item, metadata=metadata, query=query)
                for item in matches_raw
            ),
            interval_candidate_count=value["interval_candidate_count"],
            rows_scanned=value["rows_scanned"],
            context_rejected_count=value["context_rejected_count"],
            filter_rejected_count=value["filter_rejected_count"],
            total_match_count=value["total_match_count"],
            offset=value["offset"],
            limit=value["limit"],
            truncated=value["truncated"],
            warnings=tuple(warnings),
            content_address=value["content_address"],
        )
        canonical = _canonical_track_report(result, expected_query=expected_query)
    except ValidationError:
        raise
    except Exception as exc:  # noqa: BLE001 - persisted JSON is hostile
        raise ValidationError("persisted track report is invalid") from exc
    if canonical_bytes(canonical.to_dict()) != canonical_bytes(value):
        raise ValidationError("persisted track report is not an exact canonical representation")
    return canonical


def _snapshot_track_registry(
    value: ReferenceTrackAdapterRegistry,
) -> ReferenceTrackAdapterRegistry:
    try:
        adapters = value.list()
        if type(adapters) is not tuple or len(adapters) > _HARD_TRACK_REPORTS:
            raise ValidationError("atlas track adapter registry exceeds the adapter ceiling")
        snapshots = tuple(
            DeclaredReferenceTrackAdapter.from_dict(adapter.to_dict()) for adapter in adapters
        )
    except ValidationError:
        raise
    except Exception as exc:  # noqa: BLE001 - mutable registry boundary
        raise ValidationError("atlas track adapter registry is malformed") from exc
    return ReferenceTrackAdapterRegistry(snapshots)


def _motif_from_dict(raw: Mapping[str, Any]) -> MotifDefinition:
    value = _exact_object(
        raw,
        "atlas replay motif",
        frozenset({"motif_id", "name", "pattern", "source_id"}),
    )
    try:
        result = _canonical_motifs(
            (
                MotifDefinition(
                    motif_id=value["motif_id"],
                    name=value["name"],
                    pattern=value["pattern"],
                    source_id=value["source_id"],
                ),
            )
        )[0]
    except ValidationError:
        raise
    except Exception as exc:  # noqa: BLE001 - persisted JSON is hostile
        raise ValidationError("atlas replay motif is invalid") from exc
    if canonical_bytes(result.to_dict()) != canonical_bytes(value):
        raise ValidationError("atlas replay motif is not an exact canonical representation")
    return result


def _domain_profile_from_dict(raw: Mapping[str, Any]) -> DomainProfile:
    value = _exact_object(
        raw,
        "atlas replay domain profile",
        frozenset(
            {
                "profile_id",
                "context_key",
                "required_features",
                "feature_ranges",
                "source_version",
                "model_digest",
                "watch_threshold",
            }
        ),
    )
    required = _exact_array(
        value["required_features"],
        "atlas replay domain required_features",
        maximum=_HARD_UNCERTAINTY_COMPONENTS,
    )
    raw_ranges = value["feature_ranges"]
    if type(raw_ranges) is not dict or any(type(key) is not str for key in raw_ranges):
        raise ValidationError("atlas replay domain feature_ranges must be an exact JSON object")
    if len(raw_ranges) > _HARD_UNCERTAINTY_COMPONENTS:
        raise ValidationError("atlas replay domain feature_ranges exceeds the atlas ceiling")
    ranges: dict[str, tuple[float, float]] = {}
    for name, raw_bounds in raw_ranges.items():
        bounds = _exact_array(
            raw_bounds,
            f"atlas replay domain feature_ranges.{name}",
            maximum=2,
        )
        if len(bounds) != 2:
            raise ValidationError("atlas replay domain feature bounds require two values")
        ranges[name] = (bounds[0], bounds[1])
    try:
        result = _canonical_domain_profile(
            DomainProfile(
                profile_id=value["profile_id"],
                context_key=value["context_key"],
                required_features=tuple(required),
                feature_ranges=ranges,
                source_version=value["source_version"],
                model_digest=value["model_digest"],
                watch_threshold=value["watch_threshold"],
            )
        )
    except ValidationError:
        raise
    except Exception as exc:  # noqa: BLE001 - persisted JSON is hostile
        raise ValidationError("atlas replay domain profile is invalid") from exc
    if canonical_bytes(result.to_dict()) != canonical_bytes(value):
        raise ValidationError(
            "atlas replay domain profile is not an exact canonical representation"
        )
    return result


def _canonical_source_payload(value: object) -> SourcePayload:
    if type(value) is not SourcePayload:
        raise ValidationError("atlas ENCODE replay payload must be a SourcePayload")
    try:
        result = SourcePayload(
            value=value.value,
            receipt=_canonical_receipt(value.receipt, "atlas ENCODE replay receipt"),
            content_type=value.content_type,
        )
        _bounded_canonical_bytes(
            result.to_dict(),
            "atlas ENCODE replay payload",
            _HARD_BUNDLE_BYTES,
        )
    except ValidationError:
        raise
    except Exception as exc:  # noqa: BLE001 - forged exact dataclass
        raise ValidationError("atlas ENCODE replay payload is malformed") from exc
    return result


def _source_payload_from_dict(raw: Mapping[str, Any]) -> SourcePayload:
    value = _exact_object(
        raw,
        "atlas ENCODE replay payload",
        frozenset({"value", "receipt", "content_type"}),
    )
    _bounded_canonical_bytes(value, "atlas ENCODE replay payload", _HARD_BUNDLE_BYTES)
    receipt_raw = value["receipt"]
    if type(receipt_raw) is not dict:
        raise ValidationError("atlas ENCODE replay payload receipt must be an exact JSON object")
    try:
        result = _canonical_source_payload(
            SourcePayload(
                value=value["value"],
                receipt=FetchReceipt.from_dict(receipt_raw),
                content_type=value["content_type"],
            )
        )
    except ValidationError:
        raise
    except Exception as exc:  # noqa: BLE001 - persisted JSON is hostile
        raise ValidationError("atlas ENCODE replay payload is invalid") from exc
    if canonical_bytes(result.to_dict()) != canonical_bytes(value):
        raise ValidationError(
            "atlas ENCODE replay payload is not an exact canonical representation"
        )
    return result


def _canonical_replay_track_adapters(
    value: object,
) -> tuple[DeclaredReferenceTrackAdapter, ...]:
    if type(value) is not tuple or len(value) > _HARD_TRACK_REPORTS:
        raise ValidationError(
            f"atlas replay track adapters must be a tuple of at most {_HARD_TRACK_REPORTS} items"
        )
    snapshots: list[DeclaredReferenceTrackAdapter] = []
    encoded_inputs: list[bytes] = []
    for item in value:
        if type(item) is not DeclaredReferenceTrackAdapter:
            raise ValidationError(
                "atlas replay track adapters must contain declared adapter snapshots"
            )
        try:
            raw = item.to_dict()
            snapshot = DeclaredReferenceTrackAdapter.from_dict(raw)
        except ValidationError:
            raise
        except Exception as exc:  # noqa: BLE001 - forged exact dataclass
            raise ValidationError("atlas replay track adapter is malformed") from exc
        encoded_input = canonical_bytes(raw)
        if encoded_input != canonical_bytes(snapshot.to_dict()):
            raise ValidationError(
                "atlas replay track adapter is not an exact canonical representation"
            )
        snapshots.append(snapshot)
        encoded_inputs.append(encoded_input)
    identifiers = tuple(item.metadata.adapter_id for item in snapshots)
    if len(identifiers) != len(set(identifiers)):
        raise ValidationError("atlas replay track adapter identifiers must be unique")
    canonical = tuple(sorted(snapshots, key=lambda item: item.metadata.adapter_id))
    if tuple(encoded_inputs) != tuple(canonical_bytes(item.to_dict()) for item in canonical):
        raise ValidationError("atlas replay track adapters must use canonical order")
    return canonical


def _track_adapter_from_dict(raw: Mapping[str, Any]) -> DeclaredReferenceTrackAdapter:
    if type(raw) is not dict or any(type(key) is not str for key in raw):
        raise ValidationError("atlas replay track adapter must be an exact JSON object")
    try:
        result = DeclaredReferenceTrackAdapter.from_dict(raw)
    except ValidationError:
        raise
    except Exception as exc:  # noqa: BLE001 - persisted JSON is hostile
        raise ValidationError("atlas replay track adapter is invalid") from exc
    if canonical_bytes(result.to_dict()) != canonical_bytes(raw):
        raise ValidationError(
            "atlas replay track adapter is not an exact canonical representation"
        )
    return result


def _validate_encode_replay_fields(
    *,
    query: AtlasQuery,
    state: AtlasEncodeReplayState,
    payload: SourcePayload | None,
    failure_receipt: FetchReceipt | None,
    failure_warning: str | None,
) -> None:
    if not query.include_encode_catalog:
        if state is not AtlasEncodeReplayState.NOT_REQUESTED:
            raise ValidationError("unrequested ENCODE replay state must be not_requested")
    elif state is AtlasEncodeReplayState.NOT_REQUESTED:
        raise ValidationError("requested ENCODE replay state cannot be not_requested")

    if state is AtlasEncodeReplayState.PAYLOAD:
        if payload is None or failure_receipt is not None or failure_warning is not None:
            raise ValidationError("ENCODE payload replay state has inconsistent fields")
        if payload.receipt.source_id != PublicAtlasRetriever._ENCODE_SOURCE:
            raise ValidationError("ENCODE replay payload receipt uses the wrong source")
        return
    if payload is not None:
        raise ValidationError("non-payload ENCODE replay state cannot retain a payload")

    if state is AtlasEncodeReplayState.FAILURE:
        if failure_warning is None:
            raise ValidationError("ENCODE failure replay state requires a warning")
        if failure_receipt is not None:
            if failure_receipt.source_id != PublicAtlasRetriever._ENCODE_SOURCE:
                raise ValidationError("ENCODE failure receipt uses the wrong source")
        return
    if failure_receipt is not None or failure_warning is not None:
        raise ValidationError("non-failure ENCODE replay state cannot retain failure fields")


@dataclass(frozen=True, slots=True)
class AtlasReplayInputs:
    """Externally persisted inputs sufficient for deterministic offline Atlas replay."""

    variant_id: str
    variant_address: str
    context_key: str
    context_address: str
    query: AtlasQuery
    reference_bundle_address: str
    motifs: tuple[MotifDefinition, ...]
    domain_profile: DomainProfile | None
    track_adapters: tuple[DeclaredReferenceTrackAdapter, ...]
    encode_state: AtlasEncodeReplayState
    encode_payload: SourcePayload | None
    encode_failure_receipt: FetchReceipt | None
    encode_failure_warning: str | None
    content_address: str

    @staticmethod
    def _content_payload(
        *,
        variant_id: str,
        variant_address: str,
        context_key: str,
        context_address: str,
        query: AtlasQuery,
        reference_bundle_address: str,
        motifs: tuple[MotifDefinition, ...],
        domain_profile: DomainProfile | None,
        track_adapters: tuple[DeclaredReferenceTrackAdapter, ...],
        encode_state: AtlasEncodeReplayState,
        encode_payload: SourcePayload | None,
        encode_failure_receipt: FetchReceipt | None,
        encode_failure_warning: str | None,
    ) -> dict[str, Any]:
        return {
            "schema_version": _ATLAS_REPLAY_INPUTS_VERSION,
            "variant_id": variant_id,
            "variant_address": variant_address,
            "context_key": context_key,
            "context_address": context_address,
            "query": query.to_dict(),
            "reference_bundle_address": reference_bundle_address,
            "motifs": [item.to_dict() for item in motifs],
            "domain_profile": None if domain_profile is None else domain_profile.to_dict(),
            "track_adapters": [item.to_dict() for item in track_adapters],
            "encode_state": encode_state.value,
            "encode_payload": None if encode_payload is None else encode_payload.to_dict(),
            "encode_failure_receipt": (
                None if encode_failure_receipt is None else encode_failure_receipt.to_dict()
            ),
            "encode_failure_warning": encode_failure_warning,
        }

    @classmethod
    def create(
        cls,
        *,
        variant: VariantIdentity,
        context: ReferenceContext,
        query: AtlasQuery,
        reference_bundle: ReferenceBundle,
        motifs: tuple[MotifDefinition, ...] = (),
        domain_profile: DomainProfile | None = None,
        track_adapters: ReferenceTrackAdapterRegistry | None = None,
        encode_state: AtlasEncodeReplayState = AtlasEncodeReplayState.NOT_REQUESTED,
        encode_payload: SourcePayload | None = None,
        encode_failure_receipt: FetchReceipt | None = None,
        encode_failure_warning: str | None = None,
    ) -> AtlasReplayInputs:
        selected_variant = _canonical_variant(variant)
        selected_context = _canonical_context(context)
        if selected_variant.genome_build != selected_context.genome_build:
            raise ValidationError("atlas replay variant and context genome builds must match")
        selected_query = _canonical_query(query, selected_variant.variant_id)
        selected_reference = _canonical_reference_bundle(
            reference_bundle,
            variant=selected_variant,
            context=selected_context,
            window_bp=selected_query.window_bp,
        )
        selected_motifs = _canonical_motifs(motifs)
        selected_profile = (
            None if domain_profile is None else _canonical_domain_profile(domain_profile)
        )
        if selected_profile is not None and selected_profile.context_key != selected_context.key:
            raise ValidationError("atlas replay domain profile does not match its context")
        if track_adapters is not None and type(track_adapters) is not ReferenceTrackAdapterRegistry:
            raise ValidationError("atlas replay track_adapters must be a registry or None")
        selected_tracks = (
            ()
            if track_adapters is None
            else _canonical_replay_track_adapters(
                _snapshot_track_registry(track_adapters).list()
            )
        )
        if type(encode_state) is not AtlasEncodeReplayState:
            raise ValidationError("atlas encode replay state must be an AtlasEncodeReplayState")
        selected_payload = (
            None if encode_payload is None else _canonical_source_payload(encode_payload)
        )
        selected_failure_receipt = (
            None
            if encode_failure_receipt is None
            else _canonical_receipt(
                encode_failure_receipt,
                "atlas ENCODE replay failure receipt",
            )
        )
        selected_failure_warning = _optional_text(
            encode_failure_warning,
            "atlas ENCODE replay failure warning",
        )
        _validate_encode_replay_fields(
            query=selected_query,
            state=encode_state,
            payload=selected_payload,
            failure_receipt=selected_failure_receipt,
            failure_warning=selected_failure_warning,
        )
        payload = cls._content_payload(
            variant_id=selected_variant.variant_id,
            variant_address=_variant_scope_address(selected_variant),
            context_key=selected_context.key,
            context_address=_context_scope_address(selected_context),
            query=selected_query,
            reference_bundle_address=selected_reference.content_address,
            motifs=selected_motifs,
            domain_profile=selected_profile,
            track_adapters=selected_tracks,
            encode_state=encode_state,
            encode_payload=selected_payload,
            encode_failure_receipt=selected_failure_receipt,
            encode_failure_warning=selected_failure_warning,
        )
        _bounded_canonical_bytes(payload, "atlas replay inputs", _HARD_BUNDLE_BYTES)
        return cls(
            variant_id=selected_variant.variant_id,
            variant_address=_variant_scope_address(selected_variant),
            context_key=selected_context.key,
            context_address=_context_scope_address(selected_context),
            query=selected_query,
            reference_bundle_address=selected_reference.content_address,
            motifs=selected_motifs,
            domain_profile=selected_profile,
            track_adapters=selected_tracks,
            encode_state=encode_state,
            encode_payload=selected_payload,
            encode_failure_receipt=selected_failure_receipt,
            encode_failure_warning=selected_failure_warning,
            content_address=content_hash(payload),
        )

    def __post_init__(self) -> None:
        variant_id = _required_text(
            self.variant_id,
            "atlas replay variant_id",
            maximum=_HARD_IDENTIFIER_LENGTH,
        )
        variant_address = _content_address(self.variant_address, "atlas replay variant_address")
        context_key = _required_text(self.context_key, "atlas replay context_key")
        context_address = _content_address(self.context_address, "atlas replay context_address")
        query = _canonical_query(self.query, variant_id)
        reference_address = _content_address(
            self.reference_bundle_address,
            "atlas replay reference_bundle_address",
            sha256=True,
        )
        motifs = _canonical_motifs(self.motifs)
        if motifs != self.motifs:
            raise ValidationError("atlas replay motifs must use canonical order")
        profile = (
            None if self.domain_profile is None else _canonical_domain_profile(self.domain_profile)
        )
        if profile is not None and profile.context_key != context_key:
            raise ValidationError("atlas replay domain profile does not match its context")
        tracks = _canonical_replay_track_adapters(self.track_adapters)
        selected_payload = (
            None if self.encode_payload is None else _canonical_source_payload(self.encode_payload)
        )
        selected_failure_receipt = (
            None
            if self.encode_failure_receipt is None
            else _canonical_receipt(
                self.encode_failure_receipt,
                "atlas ENCODE replay failure receipt",
            )
        )
        selected_failure_warning = _optional_text(
            self.encode_failure_warning,
            "atlas ENCODE replay failure warning",
        )
        if type(self.encode_state) is not AtlasEncodeReplayState:
            raise ValidationError("atlas encode replay state must be an AtlasEncodeReplayState")
        _validate_encode_replay_fields(
            query=query,
            state=self.encode_state,
            payload=selected_payload,
            failure_receipt=selected_failure_receipt,
            failure_warning=selected_failure_warning,
        )
        payload = self._content_payload(
            variant_id=variant_id,
            variant_address=variant_address,
            context_key=context_key,
            context_address=context_address,
            query=query,
            reference_bundle_address=reference_address,
            motifs=motifs,
            domain_profile=profile,
            track_adapters=tracks,
            encode_state=self.encode_state,
            encode_payload=selected_payload,
            encode_failure_receipt=selected_failure_receipt,
            encode_failure_warning=selected_failure_warning,
        )
        _bounded_canonical_bytes(payload, "atlas replay inputs", _HARD_BUNDLE_BYTES)
        supplied_address = _content_address(
            self.content_address,
            "atlas replay inputs content_address",
            sha256=True,
        )
        if supplied_address != content_hash(payload):
            raise ValidationError("atlas replay inputs content_address does not match its payload")
        object.__setattr__(self, "query", query)
        object.__setattr__(self, "motifs", motifs)
        object.__setattr__(self, "domain_profile", profile)
        object.__setattr__(self, "track_adapters", tracks)
        object.__setattr__(self, "encode_payload", selected_payload)
        object.__setattr__(self, "encode_failure_receipt", selected_failure_receipt)
        object.__setattr__(self, "encode_failure_warning", selected_failure_warning)

    def to_dict(self) -> dict[str, Any]:
        self.__post_init__()
        return self._content_payload(
            variant_id=self.variant_id,
            variant_address=self.variant_address,
            context_key=self.context_key,
            context_address=self.context_address,
            query=self.query,
            reference_bundle_address=self.reference_bundle_address,
            motifs=self.motifs,
            domain_profile=self.domain_profile,
            track_adapters=self.track_adapters,
            encode_state=self.encode_state,
            encode_payload=self.encode_payload,
            encode_failure_receipt=self.encode_failure_receipt,
            encode_failure_warning=self.encode_failure_warning,
        ) | {"content_address": self.content_address}

    @classmethod
    def from_dict(
        cls,
        raw: Mapping[str, Any],
        variant: VariantIdentity,
        context: ReferenceContext,
        *,
        reference_bundle: ReferenceBundle,
    ) -> AtlasReplayInputs:
        value = _exact_object(
            raw,
            "atlas replay inputs",
            frozenset(
                {
                    "schema_version",
                    "variant_id",
                    "variant_address",
                    "context_key",
                    "context_address",
                    "query",
                    "reference_bundle_address",
                    "motifs",
                    "domain_profile",
                    "track_adapters",
                    "encode_state",
                    "encode_payload",
                    "encode_failure_receipt",
                    "encode_failure_warning",
                    "content_address",
                }
            ),
        )
        _bounded_canonical_bytes(value, "atlas replay inputs", _HARD_BUNDLE_BYTES)
        if value["schema_version"] != _ATLAS_REPLAY_INPUTS_VERSION:
            raise ValidationError("atlas replay inputs schema_version is unsupported")
        query_raw = value["query"]
        if type(query_raw) is not dict:
            raise ValidationError("atlas replay inputs query must be an exact JSON object")
        motifs_raw = _exact_array(
            value["motifs"],
            "atlas replay motifs",
            maximum=_HARD_MOTIFS,
        )
        tracks_raw = _exact_array(
            value["track_adapters"],
            "atlas replay track adapters",
            maximum=_HARD_TRACK_REPORTS,
        )
        if any(type(item) is not dict for item in (*motifs_raw, *tracks_raw)):
            raise ValidationError("atlas replay motif and track entries must be exact objects")
        profile_raw = value["domain_profile"]
        encode_payload_raw = value["encode_payload"]
        failure_receipt_raw = value["encode_failure_receipt"]
        for label, item in (
            ("domain_profile", profile_raw),
            ("encode_payload", encode_payload_raw),
            ("encode_failure_receipt", failure_receipt_raw),
        ):
            if item is not None and type(item) is not dict:
                raise ValidationError(f"atlas replay {label} must be an exact object or null")
        try:
            query = AtlasQuery.from_dict(query_raw)
            profile = (
                None
                if profile_raw is None
                else _domain_profile_from_dict(profile_raw)
            )
            adapters = tuple(_track_adapter_from_dict(item) for item in tracks_raw)
            registry = None if not adapters else ReferenceTrackAdapterRegistry(adapters)
            result = cls.create(
                variant=variant,
                context=context,
                query=query,
                reference_bundle=reference_bundle,
                motifs=tuple(_motif_from_dict(item) for item in motifs_raw),
                domain_profile=profile,
                track_adapters=registry,
                encode_state=AtlasEncodeReplayState(value["encode_state"]),
                encode_payload=(
                    None
                    if encode_payload_raw is None
                    else _source_payload_from_dict(encode_payload_raw)
                ),
                encode_failure_receipt=(
                    None
                    if failure_receipt_raw is None
                    else FetchReceipt.from_dict(failure_receipt_raw)
                ),
                encode_failure_warning=value["encode_failure_warning"],
            )
        except ValidationError:
            raise
        except Exception as exc:  # noqa: BLE001 - persisted JSON is hostile
            raise ValidationError("atlas replay inputs are invalid") from exc
        if result.content_address != value["content_address"]:
            raise ValidationError("atlas replay inputs content_address does not match its payload")
        if canonical_bytes(result.to_dict()) != canonical_bytes(value):
            raise ValidationError("atlas replay inputs are not an exact canonical representation")
        return result


def _validate_replay_inputs_scope(
    value: object,
    *,
    variant: VariantIdentity,
    context: ReferenceContext,
    query: AtlasQuery,
    reference_bundle_address: str,
) -> AtlasReplayInputs:
    if type(value) is not AtlasReplayInputs:
        raise ValidationError("atlas replay_inputs must be an AtlasReplayInputs artifact")
    value.__post_init__()
    if (
        value.variant_id != variant.variant_id
        or value.variant_address != _variant_scope_address(variant)
    ):
        raise ValidationError("atlas replay inputs do not match the variant scope")
    if value.context_key != context.key or value.context_address != _context_scope_address(context):
        raise ValidationError("atlas replay inputs do not match the context scope")
    if value.query != query:
        raise ValidationError("atlas replay inputs do not match the exact query")
    if value.reference_bundle_address != reference_bundle_address:
        raise ValidationError("atlas replay inputs do not match the reference bundle")
    return value


@dataclass(frozen=True, slots=True)
class AtlasBundle:
    """All public observations for one canonical variant, query, and context."""

    variant_id: str
    variant_address: str
    context_key: str
    context_address: str
    query: AtlasQuery
    source_bundle_address: str
    observations: tuple[AtlasObservation, ...]
    receipts: tuple[FetchReceipt, ...]
    warnings: tuple[str, ...]
    created_at: str
    content_address: str
    replay_inputs_address: str
    replay_inputs: AtlasReplayInputs = field(compare=False, repr=False)
    sequence_analysis: SequenceAnalysisResult | None = None
    uncertainty: UncertaintyReport | None = None
    track_reports: tuple[ReferenceTrackQueryReport, ...] = ()
    _reference_bundle: ReferenceBundle | None = field(
        default=None,
        compare=False,
        repr=False,
    )

    @staticmethod
    def _content_payload(
        *,
        variant_id: str,
        variant_address: str,
        context_key: str,
        context_address: str,
        query: AtlasQuery,
        source_bundle_address: str,
        replay_inputs_address: str,
        observations: tuple[AtlasObservation, ...],
        receipts: tuple[FetchReceipt, ...],
        warnings: tuple[str, ...],
        created_at: str,
        sequence_analysis: SequenceAnalysisResult | None,
        uncertainty: UncertaintyReport | None,
        track_reports: tuple[ReferenceTrackQueryReport, ...],
    ) -> dict[str, Any]:
        return {
            "variant_id": variant_id,
            "variant_address": variant_address,
            "context_key": context_key,
            "context_address": context_address,
            "query": query.to_dict(),
            "source_bundle_address": source_bundle_address,
            "replay_inputs_address": replay_inputs_address,
            "observations": [item.to_dict() for item in observations],
            "receipts": [item.to_dict() for item in receipts],
            "warnings": list(warnings),
            "created_at": created_at,
            "sequence_analysis": sequence_analysis.to_dict() if sequence_analysis else None,
            "uncertainty": uncertainty.to_dict() if uncertainty else None,
            "track_reports": [item.to_dict() for item in track_reports],
        }

    @classmethod
    def create(
        cls,
        *,
        variant: VariantIdentity,
        context: ReferenceContext,
        query: AtlasQuery,
        source_bundle_address: str,
        replay_inputs: AtlasReplayInputs,
        observations: tuple[AtlasObservation, ...],
        receipts: tuple[FetchReceipt, ...],
        warnings: tuple[str, ...],
        created_at: str | None = None,
        sequence_analysis: SequenceAnalysisResult | None = None,
        uncertainty: UncertaintyReport | None = None,
        track_reports: tuple[ReferenceTrackQueryReport, ...] = (),
        reference_bundle: ReferenceBundle | None = None,
    ) -> AtlasBundle:
        selected_variant = _canonical_variant(variant)
        selected_context = _canonical_context(context)
        selected_query = _canonical_query(query, selected_variant.variant_id)
        if selected_variant.genome_build != selected_context.genome_build:
            raise ValidationError("atlas variant and context genome builds must match")
        selected_observations = _canonical_observations(observations)
        selected_receipts = _canonical_receipts(receipts)
        selected_warnings = _text_tuple(
            warnings,
            "atlas warnings",
            maximum_items=_HARD_WARNINGS,
            sort=True,
        )
        selected_reports = _canonical_track_report_tuple(track_reports)
        expected_timestamp = _bundle_created_at(selected_receipts)
        timestamp = (
            expected_timestamp
            if created_at is None
            else _utc_timestamp(created_at, "atlas created_at")
        )
        if timestamp != expected_timestamp:
            raise ValidationError("atlas created_at must equal its receipt-derived timestamp")
        analysis = (
            None if sequence_analysis is None else _canonical_sequence_analysis(sequence_analysis)
        )
        uncertainty_value = None if uncertainty is None else _canonical_uncertainty(uncertainty)
        variant_address = _variant_scope_address(selected_variant)
        context_address = _context_scope_address(selected_context)
        source_address = _content_address(
            source_bundle_address,
            "atlas source_bundle_address",
            sha256=True,
        )
        selected_replay_inputs = _validate_replay_inputs_scope(
            replay_inputs,
            variant=selected_variant,
            context=selected_context,
            query=selected_query,
            reference_bundle_address=source_address,
        )
        selected_reference = (
            None
            if reference_bundle is None
            else _canonical_reference_bundle(
                reference_bundle,
                variant=selected_variant,
                context=selected_context,
                window_bp=selected_query.window_bp,
            )
        )
        if (
            selected_reference is not None
            and selected_reference.content_address != source_address
        ):
            raise ValidationError("atlas reference attachment does not match its source address")
        payload = cls._content_payload(
            variant_id=selected_variant.variant_id,
            variant_address=variant_address,
            context_key=selected_context.key,
            context_address=context_address,
            query=selected_query,
            source_bundle_address=source_address,
            replay_inputs_address=selected_replay_inputs.content_address,
            observations=selected_observations,
            receipts=selected_receipts,
            warnings=selected_warnings,
            created_at=timestamp,
            sequence_analysis=analysis,
            uncertainty=uncertainty_value,
            track_reports=selected_reports,
        )
        return cls(
            variant_id=selected_variant.variant_id,
            variant_address=variant_address,
            context_key=selected_context.key,
            context_address=context_address,
            query=selected_query,
            source_bundle_address=source_address,
            observations=selected_observations,
            receipts=selected_receipts,
            warnings=selected_warnings,
            created_at=timestamp,
            content_address=content_hash(payload),
            replay_inputs_address=selected_replay_inputs.content_address,
            replay_inputs=selected_replay_inputs,
            sequence_analysis=analysis,
            uncertainty=uncertainty_value,
            track_reports=selected_reports,
            _reference_bundle=selected_reference,
        )

    def __post_init__(self) -> None:
        _required_text(
            self.variant_id,
            "atlas bundle variant_id",
            maximum=_HARD_IDENTIFIER_LENGTH,
        )
        _content_address(self.variant_address, "atlas variant_address")
        _required_text(self.context_key, "atlas bundle context_key")
        _content_address(self.context_address, "atlas context_address")
        if type(self.query) is not AtlasQuery or self.query.variant_id != self.variant_id:
            raise ValidationError("atlas bundle query is invalid")
        query = _canonical_query(self.query, self.variant_id)
        _content_address(
            self.source_bundle_address,
            "atlas source_bundle_address",
            sha256=True,
        )
        replay_inputs_address = _content_address(
            self.replay_inputs_address,
            "atlas replay_inputs_address",
            sha256=True,
        )
        if type(self.replay_inputs) is not AtlasReplayInputs:
            raise ValidationError("atlas bundle replay_inputs attachment is invalid")
        self.replay_inputs.__post_init__()
        if self.replay_inputs.content_address != replay_inputs_address:
            raise ValidationError("atlas bundle replay inputs do not match their retained address")
        if (
            self.replay_inputs.variant_id != self.variant_id
            or self.replay_inputs.variant_address != self.variant_address
        ):
            raise ValidationError("atlas bundle replay inputs do not match its variant scope")
        if (
            self.replay_inputs.context_key != self.context_key
            or self.replay_inputs.context_address != self.context_address
        ):
            raise ValidationError("atlas bundle replay inputs do not match its context scope")
        if self.replay_inputs.query != query:
            raise ValidationError("atlas bundle replay inputs do not match its exact query")
        if self.replay_inputs.reference_bundle_address != self.source_bundle_address:
            raise ValidationError("atlas bundle replay inputs do not match its reference bundle")
        if self._reference_bundle is not None:
            if type(self._reference_bundle) is not ReferenceBundle:
                raise ValidationError("atlas reference attachment is invalid")
            self._reference_bundle.__post_init__()
            if self._reference_bundle.content_address != self.source_bundle_address:
                raise ValidationError(
                    "atlas reference attachment does not match its source address"
                )
        observations = _canonical_observations(self.observations)
        if observations != self.observations:
            raise ValidationError("atlas observations must use canonical order")
        if any(item.context_key != self.context_key for item in observations):
            raise ValidationError("atlas observation context does not match its bundle")
        receipts = _canonical_receipts(self.receipts)
        if receipts != self.receipts:
            raise ValidationError("atlas receipts must use canonical order")
        receipt_by_request = {item.request_hash: item for item in receipts}
        for observation in observations:
            if observation.receipt is None:
                continue
            if receipt_by_request.get(observation.receipt.request_hash) != observation.receipt:
                raise ValidationError("atlas observation receipt is not retained by its bundle")
        warnings = _text_tuple(
            self.warnings,
            "atlas warnings",
            maximum_items=_HARD_WARNINGS,
            sort=True,
        )
        if warnings != self.warnings:
            raise ValidationError("atlas warnings must use canonical order")
        created_at = _utc_timestamp(self.created_at, "atlas created_at")
        if created_at != _bundle_created_at(receipts):
            raise ValidationError("atlas created_at must equal its receipt-derived timestamp")
        analysis = (
            None
            if self.sequence_analysis is None
            else _canonical_sequence_analysis(self.sequence_analysis)
        )
        if analysis is not None and analysis.variant_id != self.variant_id:
            raise ValidationError("atlas sequence analysis variant_id does not match")
        uncertainty = None if self.uncertainty is None else _canonical_uncertainty(self.uncertainty)
        reports = _canonical_track_report_tuple(self.track_reports)
        if reports != self.track_reports:
            raise ValidationError("atlas track reports must use canonical order")
        if any(report.query.context_key != self.context_key for report in reports):
            raise ValidationError("atlas track report context does not match its bundle")
        evidence_ids = {
            _atlas_evidence_id(
                variant_address=self.variant_address,
                context_address=self.context_address,
                query=query,
                source_bundle_address=self.source_bundle_address,
                replay_inputs_address=replay_inputs_address,
                observation=observation,
            )
            for observation in observations
        }
        if uncertainty is not None and any(
            evidence_id not in evidence_ids
            for component in uncertainty.components
            for evidence_id in component.evidence_ids
        ):
            raise ValidationError("atlas uncertainty cites evidence outside its bundle")
        supplied_address = _content_address(
            self.content_address,
            "atlas content_address",
            sha256=True,
        )
        payload = self._content_payload(
            variant_id=self.variant_id,
            variant_address=self.variant_address,
            context_key=self.context_key,
            context_address=self.context_address,
            query=query,
            source_bundle_address=self.source_bundle_address,
            replay_inputs_address=replay_inputs_address,
            observations=observations,
            receipts=receipts,
            warnings=warnings,
            created_at=created_at,
            sequence_analysis=analysis,
            uncertainty=uncertainty,
            track_reports=reports,
        )
        try:
            encoded = canonical_bytes(payload)
        except (TypeError, ValueError, UnicodeError) as exc:
            raise ValidationError("atlas bundle payload is not canonical JSON") from exc
        if len(encoded) > _HARD_BUNDLE_BYTES:
            raise ValidationError(f"atlas bundle exceeds {_HARD_BUNDLE_BYTES} canonical bytes")
        expected = f"sha256:{hashlib.sha256(encoded).hexdigest()}"
        if supplied_address != expected:
            raise ValidationError("atlas content_address does not match its payload")
        object.__setattr__(self, "query", query)
        object.__setattr__(self, "observations", observations)
        object.__setattr__(self, "receipts", receipts)
        object.__setattr__(self, "warnings", warnings)
        object.__setattr__(self, "sequence_analysis", analysis)
        object.__setattr__(self, "uncertainty", uncertainty)
        object.__setattr__(self, "track_reports", reports)
        object.__setattr__(self, "replay_inputs", self.replay_inputs)

    def to_dict(self) -> dict[str, Any]:
        self.__post_init__()
        return self._content_payload(
            variant_id=self.variant_id,
            variant_address=self.variant_address,
            context_key=self.context_key,
            context_address=self.context_address,
            query=self.query,
            source_bundle_address=self.source_bundle_address,
            replay_inputs_address=self.replay_inputs_address,
            observations=self.observations,
            receipts=self.receipts,
            warnings=self.warnings,
            created_at=self.created_at,
            sequence_analysis=self.sequence_analysis,
            uncertainty=self.uncertainty,
            track_reports=self.track_reports,
        ) | {"content_address": self.content_address}

    @classmethod
    def from_dict(
        cls,
        raw: Mapping[str, Any],
        variant: VariantIdentity,
        context: ReferenceContext,
        *,
        reference_bundle: ReferenceBundle,
        replay_inputs: AtlasReplayInputs,
    ) -> AtlasBundle:
        """Rehydrate one exact bundle against its retained reference derivation."""

        value = _exact_object(
            raw,
            "atlas bundle",
            frozenset(
                {
                    "variant_id",
                    "variant_address",
                    "context_key",
                    "context_address",
                    "query",
                    "source_bundle_address",
                    "replay_inputs_address",
                    "observations",
                    "receipts",
                    "warnings",
                    "created_at",
                    "sequence_analysis",
                    "uncertainty",
                    "track_reports",
                    "content_address",
                }
            ),
        )
        _bounded_canonical_bytes(value, "atlas bundle", _HARD_BUNDLE_BYTES)
        selected_variant = _canonical_variant(variant)
        selected_context = _canonical_context(context)
        if selected_variant.genome_build != selected_context.genome_build:
            raise ValidationError("atlas variant and context genome builds must match")
        query_raw = value["query"]
        if type(query_raw) is not dict:
            raise ValidationError("atlas bundle query must be an exact JSON object")
        try:
            query = _canonical_query(
                AtlasQuery.from_dict(query_raw),
                selected_variant.variant_id,
            )
        except ValidationError:
            raise
        except Exception as exc:  # noqa: BLE001 - persisted JSON is hostile
            raise ValidationError("atlas bundle query is invalid") from exc
        if type(reference_bundle) is not ReferenceBundle:
            raise ValidationError("atlas reference bundle must be a ReferenceBundle")
        try:
            selected_reference = ReferenceBundle.from_dict(
                reference_bundle.to_dict(),
                selected_context,
            )
            selected_reference = _canonical_reference_bundle(
                selected_reference,
                variant=selected_variant,
                context=selected_context,
                window_bp=query.window_bp,
            )
        except ValidationError:
            raise
        except Exception as exc:  # noqa: BLE001 - retained object is a trust boundary
            raise ValidationError("atlas reference bundle is malformed") from exc
        source_address = _content_address(
            value["source_bundle_address"],
            "atlas source_bundle_address",
            sha256=True,
        )
        if source_address != selected_reference.content_address:
            raise ValidationError("atlas bundle does not bind its exact reference source bundle")
        if type(replay_inputs) is not AtlasReplayInputs:
            raise ValidationError("atlas replay_inputs must be an AtlasReplayInputs artifact")
        try:
            selected_replay_inputs = AtlasReplayInputs.from_dict(
                replay_inputs.to_dict(),
                selected_variant,
                selected_context,
                reference_bundle=selected_reference,
            )
        except ValidationError:
            raise
        except Exception as exc:  # noqa: BLE001 - retained object is a trust boundary
            raise ValidationError("atlas replay inputs are malformed") from exc
        if value["replay_inputs_address"] != selected_replay_inputs.content_address:
            raise ValidationError("atlas bundle does not bind its exact replay inputs")
        observations_raw = _exact_array(
            value["observations"],
            "atlas bundle observations",
            maximum=_HARD_OBSERVATIONS,
        )
        receipts_raw = _exact_array(
            value["receipts"],
            "atlas bundle receipts",
            maximum=_HARD_RECEIPTS,
        )
        warnings_raw = _exact_array(
            value["warnings"],
            "atlas bundle warnings",
            maximum=_HARD_WARNINGS,
        )
        track_reports_raw = _exact_array(
            value["track_reports"],
            "atlas bundle track_reports",
            maximum=_HARD_TRACK_REPORTS,
        )
        for label, items in (
            ("observations", observations_raw),
            ("receipts", receipts_raw),
            ("track_reports", track_reports_raw),
        ):
            if any(type(item) is not dict for item in items):
                raise ValidationError(f"atlas bundle {label} must contain exact JSON objects")
        sequence_raw = value["sequence_analysis"]
        uncertainty_raw = value["uncertainty"]
        if sequence_raw is not None and type(sequence_raw) is not dict:
            raise ValidationError("atlas bundle sequence_analysis must be an object or null")
        if sequence_raw is not None and selected_reference.sequence is None:
            raise ValidationError(
                "atlas sequence analysis has no retained reference sequence"
            )
        if uncertainty_raw is not None and type(uncertainty_raw) is not dict:
            raise ValidationError("atlas bundle uncertainty must be an object or null")
        chromosome, start, end = variant_interval(selected_variant)
        expected_track_query = ReferenceIndexQuery.from_mapping(
            {
                "chromosome": chromosome,
                "start": start,
                "end": end,
                "context_key": selected_context.key,
            }
        )
        try:
            result = cls(
                variant_id=value["variant_id"],
                variant_address=value["variant_address"],
                context_key=value["context_key"],
                context_address=value["context_address"],
                query=query,
                source_bundle_address=value["source_bundle_address"],
                replay_inputs_address=value["replay_inputs_address"],
                replay_inputs=selected_replay_inputs,
                observations=tuple(
                    AtlasObservation.from_dict(item) for item in observations_raw
                ),
                receipts=tuple(FetchReceipt.from_dict(item) for item in receipts_raw),
                warnings=tuple(warnings_raw),
                created_at=value["created_at"],
                content_address=value["content_address"],
                sequence_analysis=(
                    None
                    if sequence_raw is None
                    else _sequence_analysis_from_dict(
                        sequence_raw,
                        variant=selected_variant,
                        sequence=cast(SequenceSlice, selected_reference.sequence),
                    )
                ),
                uncertainty=(
                    None
                    if uncertainty_raw is None
                    else _uncertainty_from_dict(uncertainty_raw)
                ),
                track_reports=tuple(
                    _track_report_from_dict(item, expected_query=expected_track_query)
                    for item in track_reports_raw
                ),
                _reference_bundle=selected_reference,
            )
        except ValidationError:
            raise
        except Exception as exc:  # noqa: BLE001 - persisted JSON is hostile
            raise ValidationError("atlas bundle is invalid") from exc
        if (
            result.variant_id != selected_variant.variant_id
            or result.variant_address != _variant_scope_address(selected_variant)
        ):
            raise ValidationError("atlas bundle does not match its variant scope")
        if (
            result.context_key != selected_context.key
            or result.context_address != _context_scope_address(selected_context)
        ):
            raise ValidationError("atlas bundle does not match its context scope")
        _validate_retained_atlas_derivation(
            result,
            variant=selected_variant,
            reference_bundle=selected_reference,
            context=selected_context,
            replay_inputs=selected_replay_inputs,
        )
        if canonical_bytes(result.to_dict()) != canonical_bytes(value):
            raise ValidationError("atlas bundle is not an exact canonical representation")
        return result

    @property
    def abstained_count(self) -> int:
        return sum(
            observation.state is EvidenceState.ABSTAINED for observation in self.observations
        )

    def to_evidence_claims(
        self,
        *,
        variant: VariantIdentity,
        context: ReferenceContext,
        edge_id: str | None = None,
    ) -> tuple[EvidenceClaim, ...]:
        """Replay the retained derivation before exposing evidence claims."""

        selected_variant = _canonical_variant(variant)
        selected_context = _canonical_context(context)
        if _variant_scope_address(selected_variant) != self.variant_address:
            raise ValidationError("evidence variant does not match the atlas variant scope")
        if _context_scope_address(selected_context) != self.context_address:
            raise ValidationError("evidence context does not match the atlas context scope")
        self.__post_init__()
        if self._reference_bundle is None:
            raise ValidationError(
                "atlas evidence claims require an attached replay-verified reference bundle"
            )
        selected_reference = _canonical_reference_bundle(
            self._reference_bundle,
            variant=selected_variant,
            context=selected_context,
            window_bp=self.query.window_bp,
        )
        _validate_retained_atlas_derivation(
            self,
            variant=selected_variant,
            reference_bundle=selected_reference,
            context=selected_context,
            replay_inputs=self.replay_inputs,
        )
        return self._to_evidence_claims_unchecked(
            variant=selected_variant,
            context=selected_context,
            edge_id=edge_id,
        )

    def _to_evidence_claims_unchecked(
        self,
        *,
        variant: VariantIdentity,
        context: ReferenceContext,
        edge_id: str | None = None,
    ) -> tuple[EvidenceClaim, ...]:
        """Internal projection used only while deterministic replay is in progress."""

        selected_variant = _canonical_variant(variant)
        selected_context = _canonical_context(context)
        if _variant_scope_address(selected_variant) != self.variant_address:
            raise ValidationError("evidence variant does not match the atlas variant scope")
        if _context_scope_address(selected_context) != self.context_address:
            raise ValidationError("evidence context does not match the atlas context scope")
        self.__post_init__()
        edge = (
            content_hash(
                {"variant_address": self.variant_address, "channel": "public_atlas"},
                prefix="atlas-edge",
            )
            if edge_id is None
            else _required_text(edge_id, "atlas evidence edge_id", maximum=_HARD_IDENTIFIER_LENGTH)
        )
        claims: list[EvidenceClaim] = []
        for observation in self.observations:
            confidence = (
                observation.context_score
                if observation.state
                in {
                    EvidenceState.SUPPORTED,
                    EvidenceState.CONTRADICTORY,
                    EvidenceState.MEASURED_NEGATIVE,
                }
                and observation.context_score is not None
                else 0.0
            )
            # Claim identity is derived from immutable request/source scope plus the
            # observation. It deliberately excludes the final bundle address because
            # that address includes uncertainty components which themselves cite these
            # evidence identifiers.
            evidence_id = _atlas_evidence_id(
                variant_address=self.variant_address,
                context_address=self.context_address,
                query=self.query,
                source_bundle_address=self.source_bundle_address,
                replay_inputs_address=self.replay_inputs_address,
                observation=observation,
            )
            claims.append(
                EvidenceClaim(
                    evidence_id=evidence_id,
                    edge_id=edge,
                    source_id=observation.source_id,
                    channel=observation.feature_type,
                    state=observation.state,
                    tier=observation.tier,
                    score=None,
                    confidence=confidence,
                    context=selected_context,
                    summary=observation.summary,
                    payload={
                        "observation": observation.to_dict(),
                        "atlas_bundle_address": self.content_address,
                        "variant_address": self.variant_address,
                        "context_address": self.context_address,
                        "source_bundle_address": self.source_bundle_address,
                        "replay_inputs_address": self.replay_inputs_address,
                        "interpretation_boundary": (
                            "reference observation; not disease-specific mechanism evidence"
                        ),
                    },
                    produced_by="public_atlas_retriever",
                    created_at=self.created_at,
                )
            )
        return tuple(claims)


class PublicAtlasRetriever:
    """Retrieve bounded public observations without crossing source boundaries.

    Dependencies are validated once and configuration artifacts are copied into
    immutable snapshots. Retrieval is serialized because user-supplied adapters
    are not assumed to be thread-safe.
    """

    _SEQUENCE_SOURCE = "SRC-UCSC-REST"
    _FEATURE_SOURCE = "SRC-ENSEMBL-REST"
    _ENCODE_SOURCE = "SRC-ENCODE-REST"

    def __init__(
        self,
        reference_retriever: ReferenceBundleProvider | None = None,
        encode_client: EncodeProvider | None = None,
        sequence_inference: SequenceInference | None = None,
        motifs: tuple[MotifDefinition, ...] = (),
        uncertainty_propagator: UncertaintyPropagator | None = None,
        domain_profile: DomainProfile | None = None,
        track_adapters: ReferenceTrackAdapterRegistry | None = None,
    ) -> None:
        selected_reference = (
            PublicReferenceRetriever() if reference_retriever is None else reference_retriever
        )
        selected_sequence = (
            SequenceInference() if sequence_inference is None else sequence_inference
        )
        selected_uncertainty = (
            UncertaintyPropagator() if uncertainty_propagator is None else uncertainty_propagator
        )
        if not callable(getattr(selected_reference, "retrieve", None)):
            raise ValidationError("atlas reference_retriever must provide retrieve()")
        if encode_client is not None and not callable(
            getattr(encode_client, "search_experiments", None)
        ):
            raise ValidationError("atlas encode_client must provide search_experiments()")
        if not callable(getattr(selected_sequence, "analyze", None)):
            raise ValidationError("atlas sequence_inference must provide analyze()")
        if not callable(getattr(selected_uncertainty, "summarize", None)):
            raise ValidationError("atlas uncertainty_propagator must provide summarize()")
        selected_motifs = _canonical_motifs(motifs)
        selected_profile = (
            None if domain_profile is None else _canonical_domain_profile(domain_profile)
        )
        if track_adapters is not None and type(track_adapters) is not ReferenceTrackAdapterRegistry:
            raise ValidationError("atlas track_adapters must be a ReferenceTrackAdapterRegistry")
        selected_tracks = (
            None if track_adapters is None else _snapshot_track_registry(track_adapters)
        )

        self._reference_retriever = selected_reference
        self._encode_client = encode_client
        self._sequence_inference = selected_sequence
        self._motifs = selected_motifs
        self._uncertainty_propagator = selected_uncertainty
        self._domain_profile = selected_profile
        self._track_adapters = selected_tracks
        self._lock = threading.RLock()

    @property
    def reference_retriever(self) -> ReferenceBundleProvider:
        return self._reference_retriever

    @property
    def encode_client(self) -> EncodeProvider | None:
        return self._encode_client

    @property
    def sequence_inference(self) -> SequenceInference:
        return self._sequence_inference

    @property
    def motifs(self) -> tuple[MotifDefinition, ...]:
        return self._motifs

    @property
    def uncertainty_propagator(self) -> UncertaintyPropagator:
        return self._uncertainty_propagator

    @property
    def domain_profile(self) -> DomainProfile | None:
        return self._domain_profile

    @property
    def track_adapters(self) -> ReferenceTrackAdapterRegistry | None:
        # Never expose the internally frozen registry snapshot for mutation.
        if self._track_adapters is None:
            return None
        return _snapshot_track_registry(self._track_adapters)

    def retrieve(
        self,
        variant: VariantIdentity,
        context: ReferenceContext,
        *,
        query: AtlasQuery | None = None,
        reference_bundle: ReferenceBundle | None = None,
    ) -> AtlasBundle:
        coordinator = atlas_callback_scope
        if coordinator is not _callback_isolation_module.atlas_callback_scope:
            raise ValidationError("atlas callback isolation coordinator is invalid")
        with coordinator():
            return PublicAtlasRetriever._retrieve_invocation(
                self,
                variant,
                context,
                query=query,
                reference_bundle=reference_bundle,
            )

    def _retrieve_invocation(
        self,
        variant: VariantIdentity,
        context: ReferenceContext,
        *,
        query: AtlasQuery | None,
        reference_bundle: ReferenceBundle | None,
    ) -> AtlasBundle:
        expected_names = frozenset(
            {
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
        instance_state = _capture_atlas_object_configuration(
            self,
            PublicAtlasRetriever,
            expected_names,
            "public atlas retriever",
        )
        instance_namespace = instance_state.namespace
        lock_dependency = instance_namespace["_lock"]
        if type(lock_dependency) is not _RLOCK_TYPE:
            raise ValidationError("public atlas retrieval lock is invalid")
        with cast(Any, lock_dependency):
            reference_dependency = instance_namespace["_reference_retriever"]
            encode_dependency = instance_namespace["_encode_client"]
            sequence_dependency = instance_namespace["_sequence_inference"]
            uncertainty_dependency = instance_namespace["_uncertainty_propagator"]
            raw_track_registry = instance_namespace["_track_adapters"]
            raw_scanner = (
                vars(sequence_dependency).get("scanner")
                if type(sequence_dependency) is SequenceInference
                else None
            )
            nested_semantic_classes: list[type[Any]] = [
                type(reference_dependency),
                type(sequence_dependency),
                type(uncertainty_dependency),
            ]
            if encode_dependency is not None:
                nested_semantic_classes.append(type(encode_dependency))
            if raw_scanner is not None:
                nested_semantic_classes.append(type(raw_scanner))
            if raw_track_registry is not None:
                nested_semantic_classes.append(type(raw_track_registry))
            semantic_unchanged, restore_semantics = _capture_atlas_semantic_guard(
                tuple(nested_semantic_classes)
            )

            error_type = ValidationError
            canonical_encoder = canonical_bytes
            restore_instance_state = instance_state
            exception_type = Exception
            base_exception_type = BaseException
            restore_source_configuration = cast(
                Any,
                detached_callback_guard(_restore_atlas_source_configuration),
            )
            restore_object_configuration = cast(
                Any,
                detached_callback_guard(_restore_atlas_object_configuration),
            )
            restore_track_configuration = cast(
                Any,
                detached_callback_guard(_restore_atlas_track_configuration),
            )
            restore_callable_configuration = cast(
                Any,
                detached_callback_guard(_restore_atlas_callable_configuration),
            )
            callable_states: tuple[_AtlasCallableConfiguration, ...] = ()
            nested_object_states: tuple[_AtlasObjectConfiguration, ...] = ()
            source_states: tuple[_AtlasSourceConfiguration, ...] = ()
            track_configuration: _AtlasTrackConfiguration | None = None
            integrity_ready = False

            try:
                selected_callables = [
                    _capture_atlas_callable_configuration(
                        reference_dependency,
                        "retrieve",
                        "atlas reference dependency retrieve",
                    ),
                    _capture_atlas_callable_configuration(
                        sequence_dependency,
                        "analyze",
                        "atlas sequence dependency analyze",
                    ),
                    _capture_atlas_callable_configuration(
                        uncertainty_dependency,
                        "summarize",
                        "atlas uncertainty dependency summarize",
                    ),
                ]
                if encode_dependency is not None:
                    selected_callables.append(
                        _capture_atlas_callable_configuration(
                            encode_dependency,
                            "search_experiments",
                            "atlas ENCODE dependency search",
                        )
                    )
                selected_nested_objects: list[_AtlasObjectConfiguration] = []
                if type(sequence_dependency) is SequenceInference:
                    sequence_state = _capture_atlas_object_configuration(
                        sequence_dependency,
                        SequenceInference,
                        frozenset({"scanner"}),
                        "atlas sequence inference",
                    )
                    selected_nested_objects.append(sequence_state)
                    scanner = sequence_state.namespace["scanner"]
                    selected_callables.append(
                        _capture_atlas_callable_configuration(
                            scanner,
                            "scan",
                            "atlas motif scanner scan",
                        )
                    )
                    if type(scanner) is MotifScanner:
                        selected_nested_objects.append(
                            _capture_atlas_object_configuration(
                                scanner,
                                MotifScanner,
                                frozenset(),
                                "atlas motif scanner",
                            )
                        )
                if type(uncertainty_dependency) is UncertaintyPropagator:
                    selected_nested_objects.append(
                        _capture_atlas_object_configuration(
                            uncertainty_dependency,
                            UncertaintyPropagator,
                            frozenset(),
                            "atlas uncertainty propagator",
                        )
                    )
                callable_states = tuple(selected_callables)
                nested_object_states = tuple(selected_nested_objects)
                selected_sources = tuple(
                    state
                    for state in (
                        _capture_known_source_configuration(
                            reference_dependency,
                            "atlas public reference dependency",
                        ),
                        _capture_known_source_configuration(
                            encode_dependency,
                            "atlas ENCODE dependency",
                        ),
                    )
                    if state is not None
                )
                source_states = selected_sources
                if raw_track_registry is not None:
                    track_configuration = _capture_atlas_track_configuration(
                        raw_track_registry
                    )

                motif_snapshot = _canonical_motifs(instance_namespace["_motifs"])
                raw_profile = instance_namespace["_domain_profile"]
                profile_snapshot = (
                    None
                    if raw_profile is None
                    else _canonical_domain_profile(cast(DomainProfile, raw_profile))
                )
                track_snapshot = (
                    None
                    if raw_track_registry is None
                    else _snapshot_track_registry(
                        cast(ReferenceTrackAdapterRegistry, raw_track_registry)
                    )
                )
                configuration_snapshot = canonical_encoder(
                    {
                        "motifs": [item.to_dict() for item in motif_snapshot],
                        "domain_profile": (
                            None if profile_snapshot is None else profile_snapshot.to_dict()
                        ),
                        "track_adapters": (
                            None
                            if track_snapshot is None
                            else [item.to_dict() for item in track_snapshot.list()]
                        ),
                    }
                )
                clean_attributes = dict(instance_state.attributes)
                clean_attributes.update(
                    {
                        "_reference_retriever": reference_dependency,
                        "_encode_client": encode_dependency,
                        "_sequence_inference": sequence_dependency,
                        "_motifs": motif_snapshot,
                        "_uncertainty_propagator": uncertainty_dependency,
                        "_domain_profile": profile_snapshot,
                        "_track_adapters": track_snapshot,
                        "_lock": lock_dependency,
                    }
                )
                restore_instance_state = _AtlasObjectConfiguration(
                    target=self,
                    target_type=PublicAtlasRetriever,
                    namespace=instance_namespace,
                    attributes=tuple(sorted(clean_attributes.items())),
                )

                selected_variant = _canonical_variant(variant)
                selected_context = _canonical_context(context)
                if selected_variant.genome_build != selected_context.genome_build:
                    raise ValidationError("atlas variant and context genome builds must match")
                selected_query = _canonical_query(
                    (
                        AtlasQuery(variant_id=selected_variant.variant_id)
                        if query is None
                        else query
                    ),
                    selected_variant.variant_id,
                )
                selected_bundle = (
                    None
                    if reference_bundle is None
                    else _canonical_reference_bundle(
                        reference_bundle,
                        variant=selected_variant,
                        context=selected_context,
                        window_bp=selected_query.window_bp,
                    )
                )
                scope_snapshot = canonical_encoder(
                    {
                        "variant": selected_variant.to_dict(),
                        "context": selected_context.to_dict(),
                        "query": selected_query.to_dict(),
                        "reference_bundle": (
                            None if selected_bundle is None else selected_bundle.to_dict()
                        ),
                    }
                )
                def callback_integrity_is_unchanged() -> bool:
                    if not semantic_unchanged():
                        return False
                    try:
                        if (
                            not _atlas_object_configuration_unchanged(instance_state)
                            or not all(
                                _atlas_callable_configuration_unchanged(item)
                                for item in callable_states
                            )
                            or not all(
                                _atlas_object_configuration_unchanged(item)
                                for item in nested_object_states
                            )
                            or not all(
                                _atlas_source_configuration_unchanged(item)
                                for item in source_states
                            )
                            or (
                                track_configuration is not None
                                and not _atlas_track_configuration_unchanged(
                                    track_configuration
                                )
                            )
                        ):
                            return False
                        current_scope = canonical_encoder(
                            {
                                "variant": selected_variant.to_dict(),
                                "context": selected_context.to_dict(),
                                "query": selected_query.to_dict(),
                                "reference_bundle": (
                                    None
                                    if selected_bundle is None
                                    else selected_bundle.to_dict()
                                ),
                            }
                        )
                        current_motifs = _canonical_motifs(
                            instance_namespace["_motifs"]
                        )
                        current_profile_value = instance_namespace["_domain_profile"]
                        current_profile = (
                            None
                            if current_profile_value is None
                            else _canonical_domain_profile(
                                cast(DomainProfile, current_profile_value)
                            )
                        )
                        current_track_value = instance_namespace["_track_adapters"]
                        current_tracks = (
                            None
                            if current_track_value is None
                            else _snapshot_track_registry(
                                cast(ReferenceTrackAdapterRegistry, current_track_value)
                            )
                        )
                        current_configuration = canonical_encoder(
                            {
                                "motifs": [item.to_dict() for item in current_motifs],
                                "domain_profile": (
                                    None
                                    if current_profile is None
                                    else current_profile.to_dict()
                                ),
                                "track_adapters": (
                                    None
                                    if current_tracks is None
                                    else [item.to_dict() for item in current_tracks.list()]
                                ),
                            }
                        )
                        dependencies_unchanged = (
                            instance_namespace["_reference_retriever"]
                            is reference_dependency
                            and instance_namespace["_encode_client"] is encode_dependency
                            and instance_namespace["_sequence_inference"]
                            is sequence_dependency
                            and instance_namespace["_uncertainty_propagator"]
                            is uncertainty_dependency
                            and instance_namespace["_lock"] is lock_dependency
                        )
                    except exception_type:  # noqa: BLE001 - callback mutation boundary
                        return False
                    return (
                        current_scope == scope_snapshot
                        and current_configuration == configuration_snapshot
                        and dependencies_unchanged
                    )

                def assert_callback_integrity() -> None:
                    if not callback_integrity_is_unchanged():
                        raise error_type(
                            "atlas callback mutated invocation scope, retriever "
                            "configuration, or package semantics"
                        )

                integrity_ready = True
                assert_callback_integrity()
                retrieve_locked = PublicAtlasRetriever._retrieve_locked
                result = retrieve_locked(
                    self,
                    selected_variant,
                    selected_context,
                    selected_query,
                    reference_bundle=selected_bundle,
                    integrity_checkpoint=assert_callback_integrity,
                )
                assert_callback_integrity()
                return result
            finally:
                try:
                    semantic_drifted = not semantic_unchanged()
                except exception_type:  # noqa: BLE001 - callback mutation boundary
                    semantic_drifted = True
                configuration_drifted = False
                if integrity_ready:
                    try:
                        configuration_drifted = not callback_integrity_is_unchanged()
                    except exception_type:  # noqa: BLE001 - callback mutation boundary
                        configuration_drifted = True
                restoration_error: BaseException | None = None
                if semantic_drifted:
                    try:
                        restore_semantics()
                    except base_exception_type as exc:  # noqa: BLE001 - recovery must continue
                        restoration_error = exc
                for source_state in source_states:
                    try:
                        restore_source_configuration(source_state)
                    except base_exception_type as exc:  # noqa: BLE001 - recovery must continue
                        restoration_error = restoration_error or exc
                for object_state in nested_object_states:
                    try:
                        restore_object_configuration(object_state)
                    except base_exception_type as exc:  # noqa: BLE001 - recovery must continue
                        restoration_error = restoration_error or exc
                if track_configuration is not None:
                    try:
                        restore_track_configuration(track_configuration)
                    except base_exception_type as exc:  # noqa: BLE001 - recovery must continue
                        restoration_error = restoration_error or exc
                for callable_state in callable_states:
                    try:
                        restore_callable_configuration(callable_state)
                    except base_exception_type as exc:  # noqa: BLE001 - recovery must continue
                        restoration_error = restoration_error or exc
                try:
                    restore_object_configuration(restore_instance_state)
                except base_exception_type as exc:  # noqa: BLE001 - recovery must continue
                    restoration_error = restoration_error or exc
                if restoration_error is not None:
                    raise error_type(
                        "atlas callback configuration could not be restored"
                    ) from restoration_error
                if semantic_drifted:
                    raise error_type("atlas callback mutated package semantic state")
                if configuration_drifted:
                    raise error_type(
                        "atlas callback mutated invocation scope or retriever configuration"
                    )

    def _retrieve_locked(
        self,
        variant: VariantIdentity,
        context: ReferenceContext,
        query: AtlasQuery,
        *,
        reference_bundle: ReferenceBundle | None,
        integrity_checkpoint: Callable[[], None],
    ) -> AtlasBundle:
        bundle_to_dict = ReferenceBundle.to_dict
        bundle = (
            self._retrieve_reference_bundle(
                variant,
                context,
                query,
                integrity_checkpoint=integrity_checkpoint,
            )
            if reference_bundle is None
            else reference_bundle
        )
        integrity_checkpoint()
        derivation_scope_snapshot = canonical_bytes(
            {
                "variant": variant.to_dict(),
                "context": context.to_dict(),
                "query": query.to_dict(),
                "reference_bundle": bundle_to_dict(bundle),
            }
        )

        def assert_derivation_scope() -> None:
            try:
                current_scope = canonical_bytes(
                    {
                        "variant": variant.to_dict(),
                        "context": context.to_dict(),
                        "query": query.to_dict(),
                        "reference_bundle": bundle_to_dict(bundle),
                    }
                )
            except Exception as exc:  # noqa: BLE001 - callback mutation boundary
                raise ValidationError("atlas callback mutated derivation scope") from exc
            if current_scope != derivation_scope_snapshot:
                raise ValidationError("atlas callback mutated derivation scope")

        observations: list[AtlasObservation] = []
        receipts = list(bundle.receipts)
        warnings = list(bundle.warnings)

        observations.extend(self._sequence_observation(bundle, context))
        observations.extend(self._feature_observations(bundle, context))

        track_reports = self._retrieve_track_reports(variant, context)
        integrity_checkpoint()
        assert_derivation_scope()
        observations.extend(self._track_observations(track_reports, context))

        sequence_analysis: SequenceAnalysisResult | None = None
        if bundle.sequence is not None:
            if self._sequence_work_exceeds_limits(variant, bundle.sequence):
                warnings.append(_MOTIF_WORK_CEILING_WARNING)
                observations.append(self._motif_work_ceiling_observation(bundle, context))
            else:
                try:
                    raw_analysis = self._sequence_inference.analyze(
                        variant,
                        bundle.sequence,
                        motifs=self._motifs,
                    )
                except Exception as exc:  # noqa: BLE001 - dependency boundary
                    integrity_checkpoint()
                    raise ValidationError("atlas sequence inference failed") from exc
                integrity_checkpoint()
                assert_derivation_scope()
                sequence_analysis = _canonical_sequence_analysis(
                    raw_analysis,
                    variant=variant,
                    sequence=bundle.sequence,
                )
                observations.append(
                    self._sequence_analysis_observation(
                        sequence_analysis,
                        context,
                        bundle.sequence.receipt,
                    )
                )

        encode_state = AtlasEncodeReplayState.NOT_REQUESTED
        encode_payload: SourcePayload | None = None
        encode_failure_receipt: FetchReceipt | None = None
        encode_failure_warning: str | None = None
        if query.include_encode_catalog:
            encode_result = self._retrieve_encode(
                query,
                context,
                integrity_checkpoint=integrity_checkpoint,
            )
            integrity_checkpoint()
            assert_derivation_scope()
            observations.append(encode_result.observation)
            if encode_result.receipt is not None:
                receipts.append(encode_result.receipt)
            if encode_result.warning is not None:
                warnings.append(encode_result.warning)
            encode_state = encode_result.replay_state
            encode_payload = encode_result.replay_payload
            encode_failure_receipt = encode_result.failure_receipt
            encode_failure_warning = encode_result.failure_warning

        referenced_requests = {
            observation.receipt.request_hash
            for observation in observations
            if observation.receipt is not None
        }
        for receipt in receipts:
            if receipt.request_hash in referenced_requests:
                continue
            observations.append(
                self._uninterpreted_receipt_observation(
                    receipt,
                    context,
                    bundle.content_address,
                )
            )
            referenced_requests.add(receipt.request_hash)

        selected_receipts = _canonical_receipts(tuple(receipts))
        selected_warnings = _text_tuple(
            tuple(dict.fromkeys(warnings)),
            "atlas warnings",
            maximum_items=_HARD_WARNINGS,
            sort=True,
        )
        selected_observations = _canonical_observations(tuple(observations))
        replay_inputs = AtlasReplayInputs.create(
            variant=variant,
            context=context,
            query=query,
            reference_bundle=bundle,
            motifs=self._motifs,
            domain_profile=self._domain_profile,
            track_adapters=self._track_adapters,
            encode_state=encode_state,
            encode_payload=encode_payload,
            encode_failure_receipt=encode_failure_receipt,
            encode_failure_warning=encode_failure_warning,
        )

        provisional = AtlasBundle.create(
            variant=variant,
            context=context,
            query=query,
            source_bundle_address=bundle.content_address,
            replay_inputs=replay_inputs,
            observations=selected_observations,
            receipts=selected_receipts,
            warnings=selected_warnings,
            sequence_analysis=sequence_analysis,
            track_reports=track_reports,
            reference_bundle=bundle,
        )
        uncertainty = self._summarize_uncertainty(
            provisional,
            variant,
            context,
            sequence_analysis,
            integrity_checkpoint=integrity_checkpoint,
        )
        integrity_checkpoint()
        assert_derivation_scope()
        result = AtlasBundle.create(
            variant=variant,
            context=context,
            query=query,
            source_bundle_address=bundle.content_address,
            replay_inputs=replay_inputs,
            observations=selected_observations,
            receipts=selected_receipts,
            warnings=selected_warnings,
            created_at=provisional.created_at,
            sequence_analysis=sequence_analysis,
            uncertainty=uncertainty,
            track_reports=track_reports,
            reference_bundle=bundle,
        )
        assert_derivation_scope()
        _validate_retained_atlas_derivation(
            result,
            variant=variant,
            reference_bundle=bundle,
            context=context,
            replay_inputs=replay_inputs,
        )
        return result

    @staticmethod
    def _uninterpreted_receipt_observation(
        receipt: FetchReceipt,
        context: ReferenceContext,
        source_bundle_address: str,
    ) -> AtlasObservation:
        return AtlasObservation(
            observation_id=content_hash(
                {
                    "source_bundle_address": source_bundle_address,
                    "request_hash": receipt.request_hash,
                    "status": receipt.status.value,
                },
                prefix="atlas-observation",
            ),
            source_id=receipt.source_id,
            feature_type="source_retrieval",
            state=EvidenceState.ABSTAINED,
            tier=EvidenceTier.REFERENCE,
            summary="A retained source receipt had no independently usable atlas payload.",
            payload={
                "request_hash": receipt.request_hash,
                "response_hash": receipt.response_hash,
                "status": receipt.status.value,
            },
            context_key=context.key,
            context_score=None,
            receipt=receipt,
            limitations=(
                "Receipt provenance without interpreted content cannot support a conclusion.",
            ),
        )

    def _retrieve_reference_bundle(
        self,
        variant: VariantIdentity,
        context: ReferenceContext,
        query: AtlasQuery,
        *,
        integrity_checkpoint: Callable[[], None],
    ) -> ReferenceBundle:
        authority_variant = _canonical_variant(variant)
        authority_context = _canonical_context(context)
        scope_snapshot = canonical_bytes(
            {
                "variant": authority_variant.to_dict(),
                "context": authority_context.to_dict(),
            }
        )

        def scope_is_unchanged() -> bool:
            try:
                return canonical_bytes(
                    {"variant": variant.to_dict(), "context": context.to_dict()}
                ) == scope_snapshot
            except Exception:  # noqa: BLE001 - callback mutation boundary
                return False

        try:
            value = self._reference_retriever.retrieve(
                variant,
                context,
                window_bp=query.window_bp,
            )
        except Exception as error:  # noqa: BLE001 - dependency boundary
            integrity_checkpoint()
            if not isinstance(error, SourceError):
                raise
            if not scope_is_unchanged():
                raise ValidationError(
                    "atlas reference callback mutated invocation scope"
                ) from error
            receipt = _error_receipt(error)
            warning = _safe_failure("reference retrieval abstained", error)
            return ReferenceBundle.create(
                variant_id=authority_variant.variant_id,
                context=authority_context,
                sequence=None,
                elements=(),
                raw_features=(),
                receipts=() if receipt is None else (receipt,),
                warnings=(warning,),
            )
        integrity_checkpoint()
        if not scope_is_unchanged():
            raise ValidationError("atlas reference callback mutated invocation scope")
        return _canonical_reference_bundle(
            value,
            variant=authority_variant,
            context=authority_context,
            window_bp=query.window_bp,
        )

    def _retrieve_track_reports(
        self,
        variant: VariantIdentity,
        context: ReferenceContext,
    ) -> tuple[ReferenceTrackQueryReport, ...]:
        if self._track_adapters is None:
            return ()
        chromosome, start, end = variant_interval(variant)
        track_query = ReferenceIndexQuery.from_mapping(
            {
                "chromosome": chromosome,
                "start": start,
                "end": end,
                "context_key": context.key,
            }
        )
        query_snapshot = canonical_bytes(track_query.to_dict())
        try:
            raw_reports = self._track_adapters.query_all(track_query)
        except Exception as exc:  # noqa: BLE001 - adapter boundary
            raise ValidationError("atlas track adapter query failed") from exc
        try:
            current_query = canonical_bytes(track_query.to_dict())
        except Exception as exc:  # noqa: BLE001 - adapter mutation boundary
            raise ValidationError("atlas track adapter mutated its query scope") from exc
        if current_query != query_snapshot:
            raise ValidationError("atlas track adapter mutated its query scope")
        if type(raw_reports) is not tuple or len(raw_reports) > _HARD_TRACK_REPORTS:
            raise ValidationError("atlas track adapter result exceeds the report ceiling")
        reports = tuple(
            _canonical_track_report(item, expected_query=track_query) for item in raw_reports
        )
        adapter_ids = tuple(item.adapter_id for item in reports)
        if len(adapter_ids) != len(set(adapter_ids)):
            raise ValidationError("atlas track reports contain duplicate adapters")
        if sum(len(item.matches) for item in reports) > _HARD_TRACK_MATCHES:
            raise ValidationError("atlas track result exceeds the match ceiling")
        return tuple(sorted(reports, key=lambda item: item.adapter_id))

    def _retrieve_encode(
        self,
        query: AtlasQuery,
        context: ReferenceContext,
        *,
        integrity_checkpoint: Callable[[], None],
    ) -> _EncodeRetrieval:
        if self._encode_client is None:
            return _EncodeRetrieval(
                observation=self._encode_unconfigured_observation(context),
                receipt=None,
                warning=None,
                replay_state=AtlasEncodeReplayState.UNCONFIGURED,
            )
        try:
            payload = self._encode_client.search_experiments(
                assay_title=query.encode_assay_title,
                biosample_ontology_term_name=query.encode_biosample,
                limit=query.encode_limit,
            )
        except Exception as error:  # noqa: BLE001 - dependency boundary
            integrity_checkpoint()
            if isinstance(error, SourceError):
                error_receipt = _error_receipt(error, self._ENCODE_SOURCE)
                warning = _safe_failure("ENCODE catalog retrieval abstained", error)
                return _EncodeRetrieval(
                    observation=self._encode_abstention(context, warning, error_receipt),
                    receipt=error_receipt,
                    warning=warning,
                    replay_state=AtlasEncodeReplayState.FAILURE,
                    failure_receipt=error_receipt,
                    failure_warning=warning,
                )
            raise ValidationError("atlas ENCODE client failed") from error
        integrity_checkpoint()

        receipt: FetchReceipt | None = None
        retained_payload: SourcePayload | None = None
        try:
            retained_payload = _canonical_source_payload(payload)
            selected_receipt = _canonical_receipt(retained_payload.receipt, "ENCODE receipt")
            if selected_receipt.source_id != self._ENCODE_SOURCE:
                raise ValidationError("ENCODE payload receipt uses the wrong source")
            receipt = selected_receipt
            observation = self._encode_observation(
                retained_payload,
                query,
                context,
                selected_receipt,
            )
            return _EncodeRetrieval(
                observation=observation,
                receipt=selected_receipt,
                warning=None,
                replay_state=AtlasEncodeReplayState.PAYLOAD,
                replay_payload=retained_payload,
            )
        except ValidationError as error:
            # A correctly attributed receipt can still carry unusable remote content.
            # Preserve the receipt and make the failed interpretation explicit.
            if receipt is None:
                raise
            warning = _safe_failure("ENCODE catalog payload abstained", error)
            return _EncodeRetrieval(
                observation=self._encode_abstention(context, warning, receipt),
                receipt=receipt,
                warning=warning,
                replay_state=AtlasEncodeReplayState.PAYLOAD,
                replay_payload=retained_payload,
            )

    @classmethod
    def _encode_unconfigured_observation(
        cls,
        context: ReferenceContext,
    ) -> AtlasObservation:
        return AtlasObservation(
            observation_id="encode-catalog-unconfigured",
            source_id=cls._ENCODE_SOURCE,
            feature_type="assay_catalog",
            state=EvidenceState.ABSTAINED,
            tier=EvidenceTier.REFERENCE,
            summary="ENCODE catalog was requested but no client was configured.",
            payload={"requested": True},
            context_key=context.key,
            context_score=None,
            receipt=None,
            limitations=("No ENCODE request was attempted.",),
        )

    @classmethod
    def _encode_abstention(
        cls,
        context: ReferenceContext,
        reason: str,
        receipt: FetchReceipt | None,
    ) -> AtlasObservation:
        return AtlasObservation(
            observation_id=content_hash(
                {
                    "source": cls._ENCODE_SOURCE,
                    "request": None if receipt is None else receipt.request_hash,
                    "reason": reason,
                },
                prefix="atlas-observation",
            ),
            source_id=cls._ENCODE_SOURCE,
            feature_type="assay_catalog",
            state=EvidenceState.ABSTAINED,
            tier=EvidenceTier.REFERENCE,
            summary="ENCODE catalog content was unavailable or unusable; no conclusion was made.",
            payload={"reason": reason},
            context_key=context.key,
            context_score=None,
            receipt=receipt,
            limitations=("A source or payload failure is not evidence of catalog absence.",),
        )

    @classmethod
    def _encode_observation(
        cls,
        payload: SourcePayload,
        query: AtlasQuery,
        context: ReferenceContext,
        receipt: FetchReceipt,
    ) -> AtlasObservation:
        if receipt.status not in _ABSENCE_STATUSES:
            raise ValidationError("ENCODE payload carries a non-content receipt")
        if receipt.status is FetchStatus.NOT_FOUND:
            rows: tuple[Mapping[str, Any], ...] = ()
        else:
            copied = _copy_bounded_json(
                payload.value,
                label="ENCODE catalog payload",
                budget=_JsonBudget(),
            )
            media_type = payload.content_type.partition(";")[0].strip().casefold()
            if media_type != "application/json" and not media_type.endswith("+json"):
                raise ValidationError("ENCODE catalog payload is not JSON content")
            if not isinstance(copied, Mapping):
                raise ValidationError("ENCODE catalog payload must be an object")
            graph = copied.get("@graph")
            if type(graph) is not list:
                raise ValidationError("ENCODE catalog payload requires an @graph array")
            if len(graph) > query.encode_limit:
                raise ValidationError("ENCODE catalog payload exceeds the requested limit")
            if any(not isinstance(item, Mapping) for item in graph):
                raise ValidationError("ENCODE catalog @graph contains a non-object record")
            rows = tuple(cast(Mapping[str, Any], item) for item in graph)

        accessions: list[str] = []
        for index, row in enumerate(rows):
            accession = row.get("accession")
            if accession is None:
                continue
            accessions.append(
                _required_text(
                    accession,
                    f"ENCODE accession[{index}]",
                    maximum=256,
                )
            )
        accessions = sorted(set(accessions))
        state = EvidenceState.SUPPORTED if rows else EvidenceState.ABSENT
        return AtlasObservation(
            observation_id=content_hash(
                {
                    "request_hash": receipt.request_hash,
                    "response_hash": receipt.response_hash,
                    "record_count": len(rows),
                    "accessions": accessions,
                },
                prefix="atlas-observation",
            ),
            source_id=cls._ENCODE_SOURCE,
            feature_type="assay_catalog",
            state=state,
            tier=EvidenceTier.REFERENCE,
            summary=(
                f"ENCODE returned {len(rows)} experiment metadata record(s) for the "
                "declared catalog query."
            ),
            payload={
                "record_count": len(rows),
                "accessions": accessions,
                "request_hash": receipt.request_hash,
                "response_hash": receipt.response_hash,
            },
            context_key=context.key,
            context_score=None,
            receipt=receipt,
            limitations=(
                "Catalog metadata does not establish measurement of this variant or interval.",
            ),
        )

    def _sequence_work_exceeds_limits(
        self,
        variant: VariantIdentity,
        sequence: SequenceSlice,
    ) -> bool:
        return _sequence_work_exceeds_limits(variant, sequence, self._motifs)

    def _summarize_uncertainty(
        self,
        provisional: AtlasBundle,
        variant: VariantIdentity,
        context: ReferenceContext,
        sequence_analysis: SequenceAnalysisResult | None,
        *,
        integrity_checkpoint: Callable[[], None],
    ) -> UncertaintyReport:
        ood: OODAssessment | None = None
        if self._domain_profile is not None:
            if self._domain_profile.context_key != context.key:
                raise ValidationError("atlas domain profile does not match the requested context")
            ood = OutOfDomainDetector().assess(
                self._domain_features(sequence_analysis),
                self._domain_profile,
            )
            # The detector's general-purpose address includes input features that
            # are not retained in AtlasBundle. Re-address the nested assessment
            # over its complete persisted v1 preimage so replay can verify it.
            ood = _canonical_ood_assessment(ood, verify_address=False)
        claims = provisional._to_evidence_claims_unchecked(
            variant=variant,
            context=context,
        )
        try:
            raw = self._uncertainty_propagator.summarize(claims, ood=ood)
        except Exception as exc:  # noqa: BLE001 - dependency boundary
            integrity_checkpoint()
            raise ValidationError("atlas uncertainty propagation failed") from exc
        integrity_checkpoint()
        result = _canonical_uncertainty(raw)
        claim_ids = {claim.evidence_id for claim in claims}
        if any(
            evidence_id not in claim_ids
            for component in result.components
            for evidence_id in component.evidence_ids
        ):
            raise ValidationError("atlas uncertainty cites evidence outside its bundle")
        return result

    @staticmethod
    def _domain_features(analysis: SequenceAnalysisResult | None) -> dict[str, float]:
        if analysis is None:
            return {}
        features: dict[str, float] = {"motif_delta_count": float(analysis.motif_delta_count)}
        if analysis.gc_fraction_reference is not None:
            features["gc_fraction_reference"] = analysis.gc_fraction_reference
        if analysis.gc_fraction_alternate is not None:
            features["gc_fraction_alternate"] = analysis.gc_fraction_alternate
        return features

    @staticmethod
    def _source_receipt(bundle: ReferenceBundle, source_id: str) -> FetchReceipt | None:
        candidates = tuple(item for item in bundle.receipts if item.source_id == source_id)
        return candidates[0] if len(candidates) == 1 else None

    @classmethod
    def _sequence_observation(
        cls,
        bundle: ReferenceBundle,
        context: ReferenceContext,
    ) -> tuple[AtlasObservation, ...]:
        sequence = bundle.sequence
        if sequence is None:
            receipt = cls._source_receipt(bundle, cls._SEQUENCE_SOURCE)
            return (
                AtlasObservation(
                    observation_id=content_hash(
                        {
                            "source_bundle_address": bundle.content_address,
                            "feature_type": "reference_sequence",
                        },
                        prefix="atlas-observation",
                    ),
                    source_id=cls._SEQUENCE_SOURCE,
                    feature_type="reference_sequence",
                    state=EvidenceState.ABSTAINED,
                    tier=EvidenceTier.REFERENCE,
                    summary="Reference sequence retrieval did not produce usable sequence content.",
                    payload={"available": False},
                    context_key=context.key,
                    context_score=None,
                    receipt=receipt,
                    limitations=("Missing sequence content is not a sequence negative.",),
                ),
            )
        return (
            AtlasObservation(
                observation_id=content_hash(
                    {
                        "source_bundle_address": bundle.content_address,
                        "sequence": sequence.to_dict(),
                    },
                    prefix="atlas-observation",
                ),
                source_id=sequence.source_id,
                feature_type="reference_sequence",
                state=EvidenceState.SUPPORTED,
                tier=EvidenceTier.REFERENCE,
                summary=(
                    "Public reference sequence was retrieved for "
                    f"{sequence.chromosome}:{sequence.start}-{sequence.end}."
                ),
                payload={
                    "assembly": sequence.assembly,
                    "chromosome": sequence.chromosome,
                    "start": sequence.start,
                    "end": sequence.end,
                    "sequence_hash": content_hash(sequence.sequence),
                    "sequence_length": len(sequence.sequence),
                },
                context_key=context.key,
                context_score=None,
                receipt=sequence.receipt,
                limitations=(
                    "Reference sequence availability does not establish regulatory activity.",
                ),
            ),
        )

    @classmethod
    def _feature_observations(
        cls,
        bundle: ReferenceBundle,
        context: ReferenceContext,
    ) -> tuple[AtlasObservation, ...]:
        receipt = cls._source_receipt(bundle, cls._FEATURE_SOURCE)
        feature_receipts = tuple(
            item for item in bundle.receipts if item.source_id == cls._FEATURE_SOURCE
        )
        materialization_abstained = any(
            warning.casefold().startswith("candidate materialization abstained")
            for warning in bundle.warnings
        )
        retrieval_failed = (
            any(
                warning.casefold().startswith("feature retrieval abstained")
                for warning in bundle.warnings
            )
            or len(feature_receipts) != 1
            or (
                receipt is not None
                and receipt.status in {FetchStatus.FAILED, FetchStatus.RATE_LIMITED}
            )
        )
        if bundle.raw_features and retrieval_failed:
            raise ValidationError(
                "reference bundle retains features after a failed feature retrieval"
            )
        if not bundle.raw_features:
            successful_empty = (
                receipt is not None
                and receipt.status in _ABSENCE_STATUSES
                and not retrieval_failed
                and not materialization_abstained
            )
            state = EvidenceState.ABSENT if successful_empty else EvidenceState.ABSTAINED
            return (
                AtlasObservation(
                    observation_id=content_hash(
                        {
                            "source_bundle_address": bundle.content_address,
                            "feature_type": "reference_annotation",
                            "state": state,
                        },
                        prefix="atlas-observation",
                    ),
                    source_id=cls._FEATURE_SOURCE,
                    feature_type="reference_annotation",
                    state=state,
                    tier=EvidenceTier.REFERENCE,
                    summary=(
                        "The successful Ensembl query returned no overlapping annotation."
                        if successful_empty
                        else "Ensembl annotation retrieval did not produce usable content."
                    ),
                    payload={"raw_feature_count": 0},
                    context_key=context.key,
                    context_score=None,
                    receipt=receipt,
                    limitations=(
                        "No-overlap is not a negative regulatory activity measurement."
                        if successful_empty
                        else "A source failure is not evidence of annotation absence.",
                    ),
                ),
            )

        if receipt is None or receipt.status not in _SUCCESSFUL_CONTENT_STATUSES:
            return (
                AtlasObservation(
                    observation_id=content_hash(
                        {
                            "source_bundle_address": bundle.content_address,
                            "feature_type": "reference_annotation",
                            "reason": "missing_or_ambiguous_provenance",
                        },
                        prefix="atlas-observation",
                    ),
                    source_id=cls._FEATURE_SOURCE,
                    feature_type="reference_annotation",
                    state=EvidenceState.ABSTAINED,
                    tier=EvidenceTier.REFERENCE,
                    summary="Ensembl annotations lacked one usable source receipt.",
                    payload={"raw_feature_count": len(bundle.raw_features)},
                    context_key=context.key,
                    context_score=None,
                    receipt=None,
                    limitations=("Unbound source content cannot support a reference observation.",),
                ),
            )

        observations: list[AtlasObservation] = []
        for feature in bundle.raw_features:
            feature_type_value = feature.get("feature_type")
            feature_kind_is_supported = (
                type(feature_type_value) is str
                and feature_type_value.casefold() in _SUPPORTED_REFERENCE_FEATURE_TYPES
            )
            feature_type = (
                feature_type_value.casefold()
                if type(feature_type_value) is str
                and re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{0,127}", feature_type_value) is not None
                else "annotation"
            )
            feature_address = content_hash(feature, prefix="atlas-feature")
            feature_size = len(
                _bounded_canonical_bytes(
                    feature,
                    "atlas reference feature",
                    _HARD_BUNDLE_BYTES,
                )
            )
            projected_payload, projection_abstained = _project_observation_payload(
                {"feature": feature, "feature_address": feature_address},
                {
                    "feature_address": feature_address,
                    "feature_canonical_bytes": feature_size,
                    "source_bundle_address": bundle.content_address,
                },
                artifact_kind="reference_feature",
            )
            materialization_or_type_abstained = (
                materialization_abstained or not feature_kind_is_supported
            )
            feature_abstained = (
                materialization_or_type_abstained or projection_abstained
            )
            base_limitation = (
                "The raw source annotation is retained for audit only; typed "
                "candidate materialization abstained."
                if materialization_or_type_abstained
                else "Generic reference annotation is not a disease-state activity measurement."
            )
            limitations: tuple[str, ...] = (base_limitation,)
            if projection_abstained:
                limitations = _projection_limitations(
                    limitations,
                    "The complete annotation remains in the addressed reference bundle; "
                    "its Atlas observation projection exceeded the payload ceiling.",
                )
            observations.append(
                AtlasObservation(
                    observation_id=feature_address,
                    source_id=cls._FEATURE_SOURCE,
                    feature_type=f"reference_{feature_type}",
                    state=(
                        EvidenceState.ABSTAINED
                        if feature_abstained
                        else EvidenceState.SUPPORTED
                    ),
                    tier=EvidenceTier.REFERENCE,
                    summary=(
                        "Ensembl returned an annotation whose complete Atlas projection "
                        "exceeded the observation payload ceiling."
                        if projection_abstained
                        else (
                            "Ensembl returned an annotation that could not be safely "
                            "materialized as a typed candidate."
                        )
                        if materialization_or_type_abstained
                        else (
                            f"Ensembl returned one {feature_type} annotation in the "
                            "queried interval."
                        )
                    ),
                    payload=projected_payload,
                    context_key=context.key,
                    context_score=None,
                    receipt=receipt,
                    limitations=limitations,
                )
            )
        return tuple(observations)

    @staticmethod
    def _sequence_analysis_observation(
        analysis: SequenceAnalysisResult,
        context: ReferenceContext,
        receipt: FetchReceipt,
    ) -> AtlasObservation:
        if analysis.state is SequenceAnalysisState.SUPPORTED:
            state = EvidenceState.SUPPORTED
            summary = (
                "Deterministic sequence comparison found "
                f"{len(analysis.created_hits)} created and "
                f"{len(analysis.disrupted_hits)} disrupted motif hit(s)."
            )
        elif analysis.state is SequenceAnalysisState.OUT_OF_WINDOW:
            state = EvidenceState.OUT_OF_DOMAIN
            summary = "Sequence comparison was outside the retrieved reference window."
        else:
            state = EvidenceState.ABSTAINED
            summary = "Sequence comparison abstained; no motif-delta conclusion was made."
        analysis_raw = analysis.to_dict()
        projected_payload, projection_abstained = _project_observation_payload(
            {"analysis": analysis_raw},
            {
                "analysis_address": analysis.content_address,
                "analysis_canonical_bytes": len(
                    _bounded_canonical_bytes(
                        analysis_raw,
                        "atlas sequence analysis",
                        _HARD_BUNDLE_BYTES,
                    )
                ),
                "analysis_state": analysis.state.value,
                "created_hit_count": len(analysis.created_hits),
                "disrupted_hit_count": len(analysis.disrupted_hits),
                "reference_sequence_hash": analysis.reference_sequence_hash,
                "source_id": analysis.source_id,
            },
            artifact_kind="sequence_analysis",
        )
        limitations = analysis.limitations
        if projection_abstained:
            state = EvidenceState.ABSTAINED
            summary = (
                "Sequence comparison completed, but its full Atlas observation projection "
                "exceeded the payload ceiling."
            )
            limitations = _projection_limitations(
                limitations,
                "The complete sequence analysis remains in the addressed Atlas bundle; "
                "its observation projection was compacted.",
            )
        return AtlasObservation(
            observation_id=content_hash(
                {"analysis_address": analysis.content_address, "state": state},
                prefix="atlas-observation",
            ),
            source_id=analysis.source_id,
            feature_type="motif_delta",
            state=state,
            tier=EvidenceTier.COMPUTED,
            summary=summary,
            payload=projected_payload,
            context_key=context.key,
            context_score=None,
            receipt=receipt,
            limitations=limitations,
        )

    @staticmethod
    def _motif_work_ceiling_observation(
        bundle: ReferenceBundle,
        context: ReferenceContext,
    ) -> AtlasObservation:
        sequence = bundle.sequence
        if sequence is None:
            raise ValidationError("motif work abstention requires a retained reference sequence")
        return AtlasObservation(
            observation_id=content_hash(
                {
                    "source_bundle_address": bundle.content_address,
                    "feature_type": "motif_delta",
                    "reason": _MOTIF_WORK_CEILING_WARNING,
                },
                prefix="atlas-observation",
            ),
            source_id=sequence.source_id,
            feature_type="motif_delta",
            state=EvidenceState.ABSTAINED,
            tier=EvidenceTier.COMPUTED,
            summary="Sequence inference was not run because bounded work was exceeded.",
            payload={"reason": "motif_work_ceiling_exceeded"},
            context_key=context.key,
            context_score=None,
            receipt=sequence.receipt,
            limitations=(
                "No motif comparison result was inferred from an over-limit request.",
            ),
        )

    @staticmethod
    def _track_observations(
        reports: tuple[ReferenceTrackQueryReport, ...],
        context: ReferenceContext,
    ) -> tuple[AtlasObservation, ...]:
        state_map = {
            ReferenceTrackQueryState.SUPPORTED: EvidenceState.SUPPORTED,
            ReferenceTrackQueryState.TRUNCATED: EvidenceState.ABSTAINED,
            ReferenceTrackQueryState.ABSENT: EvidenceState.ABSENT,
            ReferenceTrackQueryState.OUT_OF_DOMAIN: EvidenceState.OUT_OF_DOMAIN,
            ReferenceTrackQueryState.ABSTAINED: EvidenceState.ABSTAINED,
            ReferenceTrackQueryState.INVALID: EvidenceState.ABSTAINED,
        }
        observations: list[AtlasObservation] = []
        for report in reports:
            state = state_map[report.state]
            context_score = (
                max((reading.context_score for reading in report.matches), default=None)
                if state is EvidenceState.SUPPORTED
                else None
            )
            metadata_raw = report.metadata.to_dict()
            report_raw = report.to_dict()
            projected_payload, projection_abstained = _project_observation_payload(
                {
                    "adapter_id": report.adapter_id,
                    "metadata": metadata_raw,
                    "report": report_raw,
                },
                {
                    "adapter_id": report.adapter_id,
                    "artifact_id": report.artifact_id,
                    "metadata_address": report.metadata_address,
                    "report_canonical_bytes": len(
                        _bounded_canonical_bytes(
                            report_raw,
                            "atlas track report",
                            _HARD_TRACK_REPORT_BYTES,
                        )
                    ),
                    "track_report_address": report.content_address,
                    "track_report_state": report.state.value,
                    "total_match_count": report.total_match_count,
                },
                artifact_kind="reference_track_report",
            )
            limitations, limitations_abstained = _fit_observation_limitations(
                tuple(
                    dict.fromkeys(
                        (
                            *report.metadata.limitations,
                            *report.warnings,
                            "Reference-track readings are not causal measurements.",
                        )
                    )
                ),
                "The complete track limitations remain in the addressed report; "
                "their observation projection exceeded the item ceiling.",
            )
            if projection_abstained or limitations_abstained:
                state = EvidenceState.ABSTAINED
                context_score = None
            if projection_abstained:
                limitations = _projection_limitations(
                    limitations,
                    "The complete track report remains in the addressed Atlas bundle; "
                    "its observation projection exceeded the payload ceiling.",
                )
            observations.append(
                AtlasObservation(
                    observation_id=content_hash(
                        {"track_report_address": report.content_address},
                        prefix="atlas-observation",
                    ),
                    source_id=report.metadata.source_id,
                    feature_type=f"reference_track:{report.metadata.track_type}",
                    state=state,
                    tier=EvidenceTier.REFERENCE,
                    summary=(
                        f"{report.metadata.display_name} returned a report that exceeded "
                        "the Atlas observation envelope."
                        if projection_abstained or limitations_abstained
                        else (
                            f"{report.metadata.display_name} returned {len(report.matches)} "
                            f"reading(s) with state {report.state.value}."
                        )
                    ),
                    payload=projected_payload,
                    context_key=context.key,
                    context_score=context_score,
                    receipt=None,
                    limitations=limitations,
                )
            )
        return tuple(observations)


def _sequence_work_exceeds_limits(
    variant: VariantIdentity,
    sequence: SequenceSlice,
    motifs: tuple[MotifDefinition, ...],
) -> bool:
    alternate_length = len(sequence.sequence) - len(variant.reference) + len(variant.alternate)
    comparisons = 0
    potential_hits = 0
    for motif in motifs:
        pattern = motif.normalized_pattern
        pattern_length = len(pattern)
        reference_windows = max(0, len(sequence.sequence) - pattern_length + 1)
        alternate_windows = max(0, alternate_length - pattern_length + 1)
        reverse_complement = pattern.translate(
            str.maketrans("ACGTRYSWKMBDHVN", "TGCAYRSWMKVHDBN")
        )[::-1]
        strand_count = 1 if reverse_complement == pattern else 2
        total_windows = reference_windows + alternate_windows
        # MotifScanner scans both the reference and alternate sequences and, for
        # non-palindromic motifs, both strands. Budget the exact maximum number of
        # matcher invocations and emitted raw hits rather than charging only twice
        # the larger of the two sequence-window counts.
        comparisons += total_windows * pattern_length * strand_count
        potential_hits += total_windows * strand_count
        if comparisons > _HARD_MOTIF_COMPARISONS or potential_hits > _HARD_POTENTIAL_MOTIF_HITS:
            return True
    return False


def _replay_track_reports(
    replay_inputs: AtlasReplayInputs,
    variant: VariantIdentity,
    context: ReferenceContext,
) -> tuple[ReferenceTrackQueryReport, ...]:
    if not replay_inputs.track_adapters:
        return ()
    chromosome, start, end = variant_interval(variant)
    query = ReferenceIndexQuery.from_mapping(
        {
            "chromosome": chromosome,
            "start": start,
            "end": end,
            "context_key": context.key,
        }
    )
    try:
        reports = ReferenceTrackAdapterRegistry(replay_inputs.track_adapters).query_all(query)
    except Exception as exc:  # noqa: BLE001 - replayed adapter boundary
        raise ValidationError("atlas replay track adapter query failed") from exc
    if type(reports) is not tuple or len(reports) > _HARD_TRACK_REPORTS:
        raise ValidationError("atlas replay track report ceiling was exceeded")
    selected = tuple(_canonical_track_report(item, expected_query=query) for item in reports)
    if sum(len(item.matches) for item in selected) > _HARD_TRACK_MATCHES:
        raise ValidationError("atlas replay track match ceiling was exceeded")
    return tuple(sorted(selected, key=lambda item: item.adapter_id))


def _replay_encode_observation(
    replay_inputs: AtlasReplayInputs,
    context: ReferenceContext,
) -> tuple[AtlasObservation | None, FetchReceipt | None, str | None]:
    state = replay_inputs.encode_state
    if state is AtlasEncodeReplayState.NOT_REQUESTED:
        return None, None, None
    if state is AtlasEncodeReplayState.UNCONFIGURED:
        return PublicAtlasRetriever._encode_unconfigured_observation(context), None, None
    if state is AtlasEncodeReplayState.FAILURE:
        warning = cast(str, replay_inputs.encode_failure_warning)
        receipt = replay_inputs.encode_failure_receipt
        return (
            PublicAtlasRetriever._encode_abstention(context, warning, receipt),
            receipt,
            warning,
        )

    payload = cast(SourcePayload, replay_inputs.encode_payload)
    receipt = payload.receipt
    try:
        observation = PublicAtlasRetriever._encode_observation(
            payload,
            replay_inputs.query,
            context,
            receipt,
        )
    except ValidationError as error:
        warning = _safe_failure("ENCODE catalog payload abstained", error)
        return (
            PublicAtlasRetriever._encode_abstention(context, warning, receipt),
            receipt,
            warning,
        )
    return observation, receipt, None


def _replay_uncertainty(
    *,
    variant: VariantIdentity,
    context: ReferenceContext,
    replay_inputs: AtlasReplayInputs,
    reference_bundle: ReferenceBundle,
    observations: tuple[AtlasObservation, ...],
    receipts: tuple[FetchReceipt, ...],
    warnings: tuple[str, ...],
    sequence_analysis: SequenceAnalysisResult | None,
    track_reports: tuple[ReferenceTrackQueryReport, ...],
) -> UncertaintyReport:
    provisional = AtlasBundle.create(
        variant=variant,
        context=context,
        query=replay_inputs.query,
        source_bundle_address=reference_bundle.content_address,
        replay_inputs=replay_inputs,
        observations=observations,
        receipts=receipts,
        warnings=warnings,
        sequence_analysis=sequence_analysis,
        uncertainty=None,
        track_reports=track_reports,
        reference_bundle=reference_bundle,
    )
    ood: OODAssessment | None = None
    if replay_inputs.domain_profile is not None:
        raw_ood = OutOfDomainDetector().assess(
            PublicAtlasRetriever._domain_features(sequence_analysis),
            replay_inputs.domain_profile,
        )
        ood = _canonical_ood_assessment(raw_ood, verify_address=False)
    claims = provisional._to_evidence_claims_unchecked(
        variant=variant,
        context=context,
    )
    return _canonical_uncertainty(UncertaintyPropagator().summarize(claims, ood=ood))


def _validate_retained_atlas_derivation(
    bundle: AtlasBundle,
    *,
    variant: VariantIdentity,
    reference_bundle: ReferenceBundle,
    context: ReferenceContext,
    replay_inputs: AtlasReplayInputs,
) -> None:
    """Fail closed unless every Atlas derivation replays from external exact inputs."""

    _validate_replay_inputs_scope(
        replay_inputs,
        variant=variant,
        context=context,
        query=bundle.query,
        reference_bundle_address=reference_bundle.content_address,
    )
    if bundle.replay_inputs_address != replay_inputs.content_address:
        raise ValidationError("atlas bundle does not bind the supplied replay inputs")

    atlas_receipt_by_request = {item.request_hash: item for item in bundle.receipts}
    if any(
        atlas_receipt_by_request.get(receipt.request_hash) != receipt
        for receipt in reference_bundle.receipts
    ):
        raise ValidationError("atlas receipts must retain every exact reference receipt")
    if any(warning not in bundle.warnings for warning in reference_bundle.warnings):
        raise ValidationError("atlas warnings must retain every exact reference warning")

    observations: list[AtlasObservation] = []
    observations.extend(PublicAtlasRetriever._sequence_observation(reference_bundle, context))
    observations.extend(PublicAtlasRetriever._feature_observations(reference_bundle, context))

    expected_track_reports = _replay_track_reports(replay_inputs, variant, context)
    if bundle.track_reports != expected_track_reports:
        raise ValidationError("atlas track reports do not replay from retained adapter snapshots")
    observations.extend(PublicAtlasRetriever._track_observations(expected_track_reports, context))

    atlas_warnings: list[str] = []
    expected_analysis: SequenceAnalysisResult | None = None
    if reference_bundle.sequence is not None:
        if _sequence_work_exceeds_limits(
            variant,
            reference_bundle.sequence,
            replay_inputs.motifs,
        ):
            atlas_warnings.append(_MOTIF_WORK_CEILING_WARNING)
            observations.append(
                PublicAtlasRetriever._motif_work_ceiling_observation(
                    reference_bundle,
                    context,
                )
            )
        else:
            try:
                raw_analysis = SequenceInference().analyze(
                    variant,
                    reference_bundle.sequence,
                    motifs=replay_inputs.motifs,
                )
            except Exception as exc:  # noqa: BLE001 - deterministic replay boundary
                raise ValidationError("atlas sequence inference replay failed") from exc
            expected_analysis = _canonical_sequence_analysis(
                raw_analysis,
                variant=variant,
                sequence=reference_bundle.sequence,
            )
            observations.append(
                PublicAtlasRetriever._sequence_analysis_observation(
                    expected_analysis,
                    context,
                    reference_bundle.sequence.receipt,
                )
            )

    if bundle.sequence_analysis != expected_analysis:
        raise ValidationError("atlas sequence analysis does not replay from retained inputs")

    encode_observation, encode_receipt, encode_warning = _replay_encode_observation(
        replay_inputs,
        context,
    )
    if encode_observation is not None:
        observations.append(encode_observation)
    if encode_warning is not None:
        atlas_warnings.append(encode_warning)

    receipt_inputs = list(reference_bundle.receipts)
    if encode_receipt is not None:
        receipt_inputs.append(encode_receipt)
    expected_receipts = _canonical_receipts(tuple(receipt_inputs))
    if bundle.receipts != expected_receipts:
        raise ValidationError(
            "atlas receipts must equal retained reference receipts plus classified atlas receipts"
        )

    expected_warnings = _text_tuple(
        tuple(dict.fromkeys((*reference_bundle.warnings, *atlas_warnings))),
        "atlas warnings",
        maximum_items=_HARD_WARNINGS,
        sort=True,
    )
    if bundle.warnings != expected_warnings:
        raise ValidationError(
            "atlas warnings must equal retained reference warnings plus classified atlas warnings"
        )

    referenced_requests = {
        observation.receipt.request_hash
        for observation in observations
        if observation.receipt is not None
    }
    for receipt in expected_receipts:
        if receipt.request_hash in referenced_requests:
            continue
        observations.append(
            PublicAtlasRetriever._uninterpreted_receipt_observation(
                receipt,
                context,
                reference_bundle.content_address,
            )
        )
        referenced_requests.add(receipt.request_hash)

    if bundle.observations != _canonical_observations(tuple(observations)):
        raise ValidationError(
            "atlas observations do not exactly reconstruct from retained source preimages"
        )

    expected_created_at = _bundle_created_at(expected_receipts)
    if bundle.created_at != expected_created_at:
        raise ValidationError("atlas created_at does not replay from retained receipts")

    expected_observations = _canonical_observations(tuple(observations))
    expected_uncertainty = _replay_uncertainty(
        variant=variant,
        context=context,
        replay_inputs=replay_inputs,
        reference_bundle=reference_bundle,
        observations=expected_observations,
        receipts=expected_receipts,
        warnings=expected_warnings,
        sequence_analysis=expected_analysis,
        track_reports=expected_track_reports,
    )
    if bundle.uncertainty != expected_uncertainty:
        raise ValidationError("atlas uncertainty does not replay from retained inputs")
