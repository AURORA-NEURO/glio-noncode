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
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from types import MappingProxyType
from typing import Any, Protocol, cast

from .data_sources import (
    FetchReceipt,
    FetchStatus,
    PublicReferenceRetriever,
    ReferenceBundle,
    SequenceSlice,
    SourcePayload,
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
from .reference_interval_index import ReferenceIndexQuery
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
_SUCCESSFUL_CONTENT_STATUSES = frozenset({FetchStatus.FETCHED, FetchStatus.CACHE_HIT})
_ABSENCE_STATUSES = frozenset({FetchStatus.FETCHED, FetchStatus.CACHE_HIT, FetchStatus.NOT_FOUND})
_UNINFORMATIVE_STATES = frozenset({EvidenceState.ABSTAINED, EvidenceState.OUT_OF_DOMAIN})


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


@dataclass(slots=True)
class _JsonBudget:
    nodes: int = 0
    text_characters: int = 0


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
        if type(value) is int and cast(int, value).bit_length() > 63:
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
    return content_hash(
        {
            "variant_id": variant.variant_id,
            "kind": variant.kind,
            "chromosome": variant.chromosome,
            "start": variant.start,
            "end": variant.end,
            "reference": variant.reference,
            "alternate": variant.alternate,
            "genome_build": variant.genome_build,
        },
        prefix="atlas-variant",
    )


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
        return jsonable(self)


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
        return jsonable(self)


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
    observation: AtlasObservation,
) -> str:
    return content_hash(
        {
            "variant_address": variant_address,
            "context_address": context_address,
            "query": query.to_dict(),
            "source_bundle_address": source_bundle_address,
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

    if value.state is SequenceAnalysisState.SUPPORTED:
        if variant is not None and sequence is not None:
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
        ):
            raise ValidationError("abstained sequence analysis fields are inconsistent")
        if variant is not None and sequence is not None:
            contained = variant.start >= sequence.start and variant.end <= sequence.end
            offset = variant.start - sequence.start
            actual_observed = (
                sequence.sequence[offset : offset + len(variant.reference)].upper()
                if contained
                else None
            )
            if value.state is SequenceAnalysisState.OUT_OF_WINDOW and contained:
                raise ValidationError("sequence analysis falsely reports an out-of-window state")
            if value.state is SequenceAnalysisState.REFERENCE_MISMATCH and (
                not contained
                or observed != actual_observed
                or actual_observed == variant.reference.upper()
            ):
                raise ValidationError("sequence analysis reference-mismatch state is inconsistent")
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
            if type(ood) is not OODAssessment or type(ood.status) is not OODStatus:
                raise ValidationError("uncertainty OOD assessment is invalid")
            ood = OODAssessment(
                status=ood.status,
                distance=_bounded_float(ood.distance, "OOD distance", minimum=0.0, maximum=1.0),
                missing_features=_text_tuple(
                    ood.missing_features,
                    "OOD missing_features",
                    maximum_items=_HARD_UNCERTAINTY_COMPONENTS,
                ),
                out_of_range_features=_text_tuple(
                    ood.out_of_range_features,
                    "OOD out_of_range_features",
                    maximum_items=_HARD_UNCERTAINTY_COMPONENTS,
                ),
                warnings=_text_tuple(
                    ood.warnings,
                    "OOD warnings",
                    maximum_items=_HARD_WARNINGS,
                ),
                profile_id=_required_text(ood.profile_id, "OOD profile_id", maximum=256),
                content_address=_content_address(ood.content_address, "OOD content_address"),
            )
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
        for feature in value.raw_features:
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
            context_key=value.context_key,
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
    sequence_analysis: SequenceAnalysisResult | None = None
    uncertainty: UncertaintyReport | None = None
    track_reports: tuple[ReferenceTrackQueryReport, ...] = ()

    @staticmethod
    def _content_payload(
        *,
        variant_id: str,
        variant_address: str,
        context_key: str,
        context_address: str,
        query: AtlasQuery,
        source_bundle_address: str,
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
        observations: tuple[AtlasObservation, ...],
        receipts: tuple[FetchReceipt, ...],
        warnings: tuple[str, ...],
        created_at: str | None = None,
        sequence_analysis: SequenceAnalysisResult | None = None,
        uncertainty: UncertaintyReport | None = None,
        track_reports: tuple[ReferenceTrackQueryReport, ...] = (),
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
        timestamp = (
            _bundle_created_at(selected_receipts)
            if created_at is None
            else _utc_timestamp(created_at, "atlas created_at")
        )
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
        payload = cls._content_payload(
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
            sequence_analysis=analysis,
            uncertainty=uncertainty_value,
            track_reports=selected_reports,
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

    def to_dict(self) -> dict[str, Any]:
        self.__post_init__()
        return self._content_payload(
            variant_id=self.variant_id,
            variant_address=self.variant_address,
            context_key=self.context_key,
            context_address=self.context_address,
            query=self.query,
            source_bundle_address=self.source_bundle_address,
            observations=self.observations,
            receipts=self.receipts,
            warnings=self.warnings,
            created_at=self.created_at,
            sequence_analysis=self.sequence_analysis,
            uncertainty=self.uncertainty,
            track_reports=self.track_reports,
        ) | {"content_address": self.content_address}

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
        """Convert observations without manufacturing effect scores or certainty."""

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
        return cast(ReferenceBundleProvider, self._reference_retriever)

    @property
    def encode_client(self) -> EncodeProvider | None:
        return cast(EncodeProvider | None, self._encode_client)

    @property
    def sequence_inference(self) -> SequenceInference:
        return cast(SequenceInference, self._sequence_inference)

    @property
    def motifs(self) -> tuple[MotifDefinition, ...]:
        return self._motifs

    @property
    def uncertainty_propagator(self) -> UncertaintyPropagator:
        return cast(UncertaintyPropagator, self._uncertainty_propagator)

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
    ) -> AtlasBundle:
        selected_variant = _canonical_variant(variant)
        selected_context = _canonical_context(context)
        if selected_variant.genome_build != selected_context.genome_build:
            raise ValidationError("atlas variant and context genome builds must match")
        selected_query = _canonical_query(
            AtlasQuery(variant_id=selected_variant.variant_id) if query is None else query,
            selected_variant.variant_id,
        )

        with self._lock:
            return self._retrieve_locked(selected_variant, selected_context, selected_query)

    def _retrieve_locked(
        self,
        variant: VariantIdentity,
        context: ReferenceContext,
        query: AtlasQuery,
    ) -> AtlasBundle:
        bundle = self._retrieve_reference_bundle(variant, context, query)
        observations: list[AtlasObservation] = []
        receipts = list(bundle.receipts)
        warnings = list(bundle.warnings)

        observations.extend(self._sequence_observation(bundle, context))
        observations.extend(self._feature_observations(bundle, context))

        track_reports = self._retrieve_track_reports(variant, context)
        observations.extend(self._track_observations(track_reports, context))

        sequence_analysis: SequenceAnalysisResult | None = None
        if bundle.sequence is not None:
            if self._sequence_work_exceeds_limits(variant, bundle.sequence):
                warning = "sequence inference abstained: atlas motif work ceiling exceeded"
                warnings.append(warning)
                observations.append(
                    AtlasObservation(
                        observation_id=content_hash(
                            {
                                "source_bundle_address": bundle.content_address,
                                "feature_type": "motif_delta",
                                "reason": warning,
                            },
                            prefix="atlas-observation",
                        ),
                        source_id=bundle.sequence.source_id,
                        feature_type="motif_delta",
                        state=EvidenceState.ABSTAINED,
                        tier=EvidenceTier.COMPUTED,
                        summary="Sequence inference was not run because bounded work was exceeded.",
                        payload={"reason": "motif_work_ceiling_exceeded"},
                        context_key=context.key,
                        context_score=None,
                        receipt=bundle.sequence.receipt,
                        limitations=(
                            "No motif comparison result was inferred from an over-limit request.",
                        ),
                    )
                )
            else:
                try:
                    raw_analysis = self._sequence_inference.analyze(
                        variant,
                        bundle.sequence,
                        motifs=self._motifs,
                    )
                except Exception as exc:  # noqa: BLE001 - dependency boundary
                    raise ValidationError("atlas sequence inference failed") from exc
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

        if query.include_encode_catalog:
            encode_observation, encode_receipt, encode_warning = self._retrieve_encode(
                query,
                context,
            )
            observations.append(encode_observation)
            if encode_receipt is not None:
                receipts.append(encode_receipt)
            if encode_warning is not None:
                warnings.append(encode_warning)

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

        provisional = AtlasBundle.create(
            variant=variant,
            context=context,
            query=query,
            source_bundle_address=bundle.content_address,
            observations=selected_observations,
            receipts=selected_receipts,
            warnings=selected_warnings,
            sequence_analysis=sequence_analysis,
            track_reports=track_reports,
        )
        uncertainty = self._summarize_uncertainty(provisional, variant, context, sequence_analysis)
        return AtlasBundle.create(
            variant=variant,
            context=context,
            query=query,
            source_bundle_address=bundle.content_address,
            observations=selected_observations,
            receipts=selected_receipts,
            warnings=selected_warnings,
            created_at=provisional.created_at,
            sequence_analysis=sequence_analysis,
            uncertainty=uncertainty,
            track_reports=track_reports,
        )

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
                    "status": receipt.status,
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
                "status": receipt.status,
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
    ) -> ReferenceBundle:
        try:
            value = self._reference_retriever.retrieve(
                variant,
                context,
                window_bp=query.window_bp,
            )
        except SourceError as error:
            receipt = _error_receipt(error)
            warning = _safe_failure("reference retrieval abstained", error)
            return ReferenceBundle.create(
                variant_id=variant.variant_id,
                context_key=context.key,
                sequence=None,
                elements=(),
                raw_features=(),
                receipts=() if receipt is None else (receipt,),
                warnings=(warning,),
            )
        return _canonical_reference_bundle(
            value,
            variant=variant,
            context=context,
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
        try:
            raw_reports = self._track_adapters.query_all(track_query)
        except Exception as exc:  # noqa: BLE001 - adapter boundary
            raise ValidationError("atlas track adapter query failed") from exc
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
    ) -> tuple[AtlasObservation, FetchReceipt | None, str | None]:
        if self._encode_client is None:
            return (
                AtlasObservation(
                    observation_id="encode-catalog-unconfigured",
                    source_id=self._ENCODE_SOURCE,
                    feature_type="assay_catalog",
                    state=EvidenceState.ABSTAINED,
                    tier=EvidenceTier.REFERENCE,
                    summary="ENCODE catalog was requested but no client was configured.",
                    payload={"requested": True},
                    context_key=context.key,
                    context_score=None,
                    receipt=None,
                    limitations=("No ENCODE request was attempted.",),
                ),
                None,
                None,
            )
        try:
            payload = self._encode_client.search_experiments(
                assay_title=query.encode_assay_title,
                biosample_ontology_term_name=query.encode_biosample,
                limit=query.encode_limit,
            )
        except SourceError as error:
            error_receipt = _error_receipt(error, self._ENCODE_SOURCE)
            warning = _safe_failure("ENCODE catalog retrieval abstained", error)
            return (
                self._encode_abstention(context, warning, error_receipt),
                error_receipt,
                warning,
            )
        except Exception as exc:  # noqa: BLE001 - dependency boundary
            raise ValidationError("atlas ENCODE client failed") from exc

        receipt: FetchReceipt | None = None
        try:
            if type(payload) is not SourcePayload:
                raise ValidationError("ENCODE client must return a SourcePayload")
            receipt = _canonical_receipt(payload.receipt, "ENCODE receipt")
            if receipt.source_id != self._ENCODE_SOURCE:
                raise ValidationError("ENCODE payload receipt uses the wrong source")
            observation = self._encode_observation(payload, query, context, receipt)
            return observation, receipt, None
        except ValidationError as error:
            # A correctly attributed receipt can still carry unusable remote content.
            # Preserve the receipt and make the failed interpretation explicit.
            if receipt is None:
                raise
            warning = _safe_failure("ENCODE catalog payload abstained", error)
            return self._encode_abstention(context, warning, receipt), receipt, warning

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
        alternate_length = len(sequence.sequence) - len(variant.reference) + len(variant.alternate)
        scan_length = max(len(sequence.sequence), alternate_length)
        comparisons = 0
        potential_hits = 0
        for motif in self._motifs:
            windows = max(0, scan_length - len(motif.normalized_pattern) + 1)
            comparisons += windows * len(motif.normalized_pattern) * 2
            potential_hits += windows * 2
            if comparisons > _HARD_MOTIF_COMPARISONS or potential_hits > _HARD_POTENTIAL_MOTIF_HITS:
                return True
        return False

    def _summarize_uncertainty(
        self,
        provisional: AtlasBundle,
        variant: VariantIdentity,
        context: ReferenceContext,
        sequence_analysis: SequenceAnalysisResult | None,
    ) -> UncertaintyReport:
        ood: OODAssessment | None = None
        if self._domain_profile is not None:
            if self._domain_profile.context_key != context.key:
                raise ValidationError("atlas domain profile does not match the requested context")
            ood = OutOfDomainDetector().assess(
                self._domain_features(sequence_analysis),
                self._domain_profile,
            )
        claims = provisional.to_evidence_claims(variant=variant, context=context)
        try:
            raw = self._uncertainty_propagator.summarize(claims, ood=ood)
        except Exception as exc:  # noqa: BLE001 - dependency boundary
            raise ValidationError("atlas uncertainty propagation failed") from exc
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
        failed = (
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
        if bundle.raw_features and failed:
            raise ValidationError(
                "reference bundle retains features after a failed feature retrieval"
            )
        if not bundle.raw_features:
            successful_empty = (
                receipt is not None and receipt.status in _ABSENCE_STATUSES and not failed
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
            feature_type_value = feature.get("feature_type") or feature.get("object_type")
            feature_type = (
                feature_type_value.casefold()
                if type(feature_type_value) is str
                and re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{0,127}", feature_type_value) is not None
                else "annotation"
            )
            feature_address = content_hash(feature, prefix="atlas-feature")
            observations.append(
                AtlasObservation(
                    observation_id=feature_address,
                    source_id=cls._FEATURE_SOURCE,
                    feature_type=f"reference_{feature_type}",
                    state=EvidenceState.SUPPORTED,
                    tier=EvidenceTier.REFERENCE,
                    summary=(
                        f"Ensembl returned one {feature_type} annotation in the queried interval."
                    ),
                    payload={"feature": feature, "feature_address": feature_address},
                    context_key=context.key,
                    context_score=None,
                    receipt=receipt,
                    limitations=(
                        "Generic reference annotation is not a disease-state activity measurement.",
                    ),
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
            payload={"analysis": analysis.to_dict()},
            context_key=context.key,
            context_score=None,
            receipt=receipt,
            limitations=analysis.limitations,
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
                        f"{report.metadata.display_name} returned {len(report.matches)} "
                        f"reading(s) with state {report.state.value}."
                    ),
                    payload={
                        "adapter_id": report.adapter_id,
                        "metadata": report.metadata.to_dict(),
                        "report": report.to_dict(),
                    },
                    context_key=context.key,
                    context_score=context_score,
                    receipt=None,
                    limitations=tuple(
                        dict.fromkeys(
                            (
                                *report.metadata.limitations,
                                *report.warnings,
                                "Reference-track readings are not causal measurements.",
                            )
                        )
                    ),
                )
            )
        return tuple(observations)
