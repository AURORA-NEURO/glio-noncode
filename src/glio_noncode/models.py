"""Typed domain objects for cases, evidence, hypotheses, review, and release."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from .errors import ValidationError
from .serialization import (
    canonical_bytes,
    content_hash,
    freeze_json,
    jsonable,
    require_non_empty,
    utc_now,
)


def _strict_mapping(
    raw: object,
    *,
    label: str,
    allowed: frozenset[str],
    required: frozenset[str],
) -> Mapping[str, Any]:
    if not isinstance(raw, Mapping):
        raise ValidationError(f"{label} must be an object")
    if any(type(key) is not str for key in raw):
        raise ValidationError(f"{label} keys must be strings")
    unknown = set(raw) - allowed
    if unknown:
        raise ValidationError(f"{label} contains unknown fields: {sorted(unknown)}")
    missing = required - set(raw)
    if missing:
        raise ValidationError(f"{label} is missing required fields: {sorted(missing)}")
    return raw


def _string(value: object, label: str, *, non_empty: bool = True) -> str:
    if type(value) is not str:
        raise ValidationError(f"{label} must be a string")
    if non_empty and not value.strip():
        raise ValidationError(f"{label} must not be empty")
    return value


def _integer(value: object, label: str) -> int:
    if type(value) is not int:
        raise ValidationError(f"{label} must be an integer")
    return value


def _number(value: object, label: str) -> int | float:
    if type(value) not in {int, float}:
        raise ValidationError(f"{label} must be a finite number")
    if type(value) is int:
        return value
    try:
        result = float(value)
    except OverflowError as exc:
        raise ValidationError(f"{label} must be a finite number") from exc
    if not math.isfinite(result):
        raise ValidationError(f"{label} must be a finite number")
    return result


def _boolean(value: object, label: str) -> bool:
    if type(value) is not bool:
        raise ValidationError(f"{label} must be a boolean")
    return value


def _sequence(value: object, label: str) -> list[Any] | tuple[Any, ...]:
    if not isinstance(value, (list, tuple)):
        raise ValidationError(f"{label} must be an array")
    return value


def _strings(
    value: object,
    label: str,
    *,
    non_empty: bool = False,
    unique: bool = False,
) -> tuple[str, ...]:
    values = tuple(
        _string(item, f"{label}[{index}]")
        for index, item in enumerate(_sequence(value, label))
    )
    if non_empty and not values:
        raise ValidationError(f"{label} must not be empty")
    if unique and len(values) != len(set(values)):
        raise ValidationError(f"{label} must contain unique values")
    return values


def _json_mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{label} must be an object")
    frozen = freeze_json(value, field=label)
    if not isinstance(frozen, Mapping):  # pragma: no cover - guarded above
        raise ValidationError(f"{label} must be an object")
    return frozen


def _enum(enum_type: type[ValueEnum], value: object, label: str) -> ValueEnum:
    text = _string(value, label)
    try:
        return enum_type(text)
    except ValueError as exc:
        raise ValidationError(f"{label} has unsupported value {text!r}") from exc


def _sha256_address(value: object, label: str) -> str:
    address = _string(value, label)
    if (
        len(address) != 71
        or not address.startswith("sha256:")
        or any(character not in "0123456789abcdef" for character in address[7:])
    ):
        raise ValidationError(f"{label} must be a canonical sha256 content address")
    return address


def _content_address(value: object, label: str) -> str:
    address = _string(value, label)
    prefix, separator, digest = address.rpartition(":")
    if (
        separator != ":"
        or not prefix
        or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
    ):
        raise ValidationError(f"{label} must be a canonical content address")
    return address


def _utc_timestamp(value: object, label: str) -> str:
    timestamp = _string(value, label)
    try:
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValidationError(f"{label} must be an ISO-8601 UTC timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValidationError(f"{label} must be an ISO-8601 UTC timestamp")
    return timestamp


def _require_exact_roundtrip(raw: Mapping[str, Any], value: object, label: str) -> None:
    try:
        if canonical_bytes(raw) != canonical_bytes(jsonable(value)):
            raise ValidationError(f"{label} is not an exact canonical typed representation")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise ValidationError(f"{label} must contain only canonical JSON values") from exc


class ValueEnum(str, Enum):  # noqa: UP042 - preserve historical str(member) behavior
    """Enum base whose values are stable strings in serialized contracts."""


class VariantKind(ValueEnum):
    SNV = "snv"
    INDEL = "indel"
    CNV = "cnv"
    BREAKEND = "breakend"
    HAPLOTYPE = "haplotype"


class VariantOrigin(ValueEnum):
    GERMLINE = "germline"
    SOMATIC = "somatic"
    MOSAIC = "mosaic"
    CLONAL = "clonal"
    UNCERTAIN = "uncertain"


class EvidenceState(ValueEnum):
    SUPPORTED = "supported"
    ABSENT = "absent"
    CONTRADICTORY = "contradictory"
    MEASURED_NEGATIVE = "measured_negative"
    UNSUPPORTED = "unsupported"
    OUT_OF_DOMAIN = "out_of_domain"
    ABSTAINED = "abstained"


class EvidenceTier(ValueEnum):
    REFERENCE = "reference"
    COMPUTED = "computed"
    EXPERIMENTAL = "experimental"
    COHORT = "cohort"
    REVIEWED = "reviewed"


class SupportLevel(ValueEnum):
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    UNKNOWN = "unknown"


class ResearchStatus(ValueEnum):
    DRAFT = "draft"
    REVIEW_REQUIRED = "review_required"
    REVIEWED = "reviewed"
    RELEASED_RESEARCH = "released_research"
    SUPERSEDED = "superseded"


class ReviewState(ValueEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    RETURNED = "returned"


class EdgeType(ValueEnum):
    VARIANT_TO_ELEMENT = "variant_to_element"
    ELEMENT_TO_GENE = "element_to_gene"
    GENE_TO_STATE = "gene_to_state"
    CAUSAL_PATH = "causal_path"


class AssayType(ValueEnum):
    MPRA = "mpra"
    CRISPR_INTERFERENCE = "crispri"
    CRISPR_ACTIVATION = "crispra"
    BASE_EDITING = "base_editing"
    REPORTER = "reporter"
    PERTURBATION = "perturbation"
    CONTACT_ASSAY = "contact_assay"
    RNA_MEASUREMENT = "rna_measurement"


@dataclass(frozen=True, slots=True)
class ReferenceContext:
    """The context in which evidence is applicable."""

    genome_build: str
    disease_class: str
    age_group: str
    cell_state: str
    territory: str = "unknown"
    treatment_phase: str = "unknown"
    assay_support: tuple[str, ...] = ()
    source_version: str = "unspecified"

    def __post_init__(self) -> None:
        for name in (
            "genome_build",
            "disease_class",
            "age_group",
            "cell_state",
            "territory",
            "treatment_phase",
            "source_version",
        ):
            require_non_empty(getattr(self, name), name)
        object.__setattr__(
            self,
            "assay_support",
            _strings(self.assay_support, "assay_support", unique=True),
        )

    @property
    def key(self) -> str:
        parts = (
            self.genome_build,
            self.disease_class,
            self.age_group,
            self.cell_state,
            self.territory,
            self.treatment_phase,
        )
        return "|".join(parts)

    @classmethod
    def from_dict(
        cls,
        raw: Mapping[str, Any],
        *,
        persisted: bool = False,
    ) -> ReferenceContext:
        allowed = frozenset(
            {
                "genome_build",
                "disease_class",
                "age_group",
                "cell_state",
                "territory",
                "treatment_phase",
                "assay_support",
                "source_version",
            }
        )
        required = allowed if persisted else frozenset(
            {"genome_build", "disease_class", "age_group", "cell_state"}
        )
        value = _strict_mapping(
            raw,
            label="reference context",
            allowed=allowed,
            required=required,
        )
        return cls(
            genome_build=_string(value["genome_build"], "context.genome_build"),
            disease_class=_string(value["disease_class"], "context.disease_class"),
            age_group=_string(value["age_group"], "context.age_group"),
            cell_state=_string(value["cell_state"], "context.cell_state"),
            territory=_string(value.get("territory", "unknown"), "context.territory"),
            treatment_phase=_string(
                value.get("treatment_phase", "unknown"),
                "context.treatment_phase",
            ),
            assay_support=_strings(
                value.get("assay_support", ()),
                "context.assay_support",
                unique=True,
            ),
            source_version=_string(
                value.get("source_version", "unspecified"),
                "context.source_version",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class VariantIdentity:
    """Canonical variation identity with explicit origin and provenance."""

    variant_id: str
    kind: VariantKind
    chromosome: str
    start: int
    end: int
    reference: str
    alternate: str
    genome_build: str
    origin: VariantOrigin = VariantOrigin.UNCERTAIN
    clonality: str = "unknown"
    sample_id: str = "unspecified"
    annotations: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("variant_id", "chromosome", "genome_build"):
            object.__setattr__(self, name, require_non_empty(getattr(self, name), name))
        if type(self.kind) is not VariantKind:
            raise ValidationError("variant kind must be a VariantKind")
        if type(self.origin) is not VariantOrigin:
            raise ValidationError("variant origin must be a VariantOrigin")
        start = _integer(self.start, "variant.start")
        end = _integer(self.end, "variant.end")
        if start < 1 or end < start:
            raise ValidationError("variant coordinates must satisfy 1 <= start <= end")
        object.__setattr__(self, "start", start)
        object.__setattr__(self, "end", end)
        object.__setattr__(self, "reference", require_non_empty(self.reference, "reference"))
        object.__setattr__(self, "alternate", require_non_empty(self.alternate, "alternate"))
        object.__setattr__(self, "clonality", require_non_empty(self.clonality, "clonality"))
        object.__setattr__(self, "sample_id", require_non_empty(self.sample_id, "sample_id"))
        object.__setattr__(self, "annotations", _json_mapping(self.annotations, "annotations"))

    @property
    def canonical_key(self) -> str:
        return ":".join(
            (
                self.genome_build,
                self.chromosome,
                str(self.start),
                str(self.end),
                self.reference,
                self.alternate,
            )
        )

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> VariantIdentity:
        allowed = frozenset(
            {
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
        )
        value = _strict_mapping(
            raw,
            label="variant",
            allowed=allowed,
            required=frozenset(
                {
                    "variant_id",
                    "chromosome",
                    "start",
                    "reference",
                    "alternate",
                    "genome_build",
                }
            ),
        )
        start = _integer(value["start"], "variant.start")
        return cls(
            variant_id=_string(value["variant_id"], "variant.variant_id"),
            kind=VariantKind(
                _enum(
                    VariantKind,
                    value.get("kind", VariantKind.SNV.value),
                    "variant.kind",
                )
            ),
            chromosome=_string(value["chromosome"], "variant.chromosome"),
            start=start,
            end=_integer(value.get("end", start), "variant.end"),
            reference=_string(value["reference"], "variant.reference"),
            alternate=_string(value["alternate"], "variant.alternate"),
            genome_build=_string(value["genome_build"], "variant.genome_build"),
            origin=VariantOrigin(
                _enum(
                    VariantOrigin,
                    value.get("origin", VariantOrigin.UNCERTAIN.value),
                    "variant.origin",
                )
            ),
            clonality=_string(value.get("clonality", "unknown"), "variant.clonality"),
            sample_id=_string(value.get("sample_id", "unspecified"), "variant.sample_id"),
            annotations=_json_mapping(value.get("annotations", {}), "variant.annotations"),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CandidateElement:
    """A context-qualified regulatory element candidate supplied by an adapter."""

    element_id: str
    chromosome: str
    start: int
    end: int
    element_type: str
    context: ReferenceContext
    source_id: str
    target_genes: tuple[str, ...] = ()
    state_ids: tuple[str, ...] = ()
    features: Mapping[str, float] = field(default_factory=dict)
    annotations: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("element_id", "chromosome", "element_type", "source_id"):
            object.__setattr__(self, name, require_non_empty(getattr(self, name), name))
        if type(self.context) is not ReferenceContext:
            raise ValidationError("candidate element context must be a ReferenceContext")
        start = _integer(self.start, "candidate element start")
        end = _integer(self.end, "candidate element end")
        if start < 1 or end < start:
            raise ValidationError("element coordinates must satisfy 1 <= start <= end")
        object.__setattr__(self, "start", start)
        object.__setattr__(self, "end", end)
        if not self.target_genes and not self.state_ids:
            raise ValidationError("an element must expose a candidate gene or state")
        object.__setattr__(
            self,
            "target_genes",
            _strings(self.target_genes, "target_genes", unique=True),
        )
        object.__setattr__(self, "state_ids", _strings(self.state_ids, "state_ids", unique=True))
        features = _json_mapping(self.features, "features")
        normalized_features = {
            name: _number(value, f"features.{name}") for name, value in features.items()
        }
        object.__setattr__(self, "features", _json_mapping(normalized_features, "features"))
        object.__setattr__(self, "annotations", _json_mapping(self.annotations, "annotations"))

    @classmethod
    def from_dict(
        cls,
        raw: Mapping[str, Any],
        default_context: ReferenceContext,
    ) -> CandidateElement:
        allowed = frozenset(
            {
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
        )
        value = _strict_mapping(
            raw,
            label="candidate element",
            allowed=allowed,
            required=frozenset({"element_id", "chromosome", "start", "source_id"}),
        )
        if "context" not in value:
            context = default_context
        else:
            context_raw = value["context"]
            if not isinstance(context_raw, Mapping):
                raise ValidationError("candidate element context must be an object")
            context = ReferenceContext.from_dict(context_raw)
        start = _integer(value["start"], "candidate_element.start")
        features_raw = _json_mapping(value.get("features", {}), "candidate_element.features")
        features = {
            key: _number(item, f"candidate_element.features.{key}")
            for key, item in features_raw.items()
        }
        return cls(
            element_id=_string(value["element_id"], "candidate_element.element_id"),
            chromosome=_string(value["chromosome"], "candidate_element.chromosome"),
            start=start,
            end=_integer(value.get("end", start), "candidate_element.end"),
            element_type=_string(
                value.get("element_type", "regulatory_element"),
                "candidate_element.element_type",
            ),
            context=context,
            source_id=_string(value["source_id"], "candidate_element.source_id"),
            target_genes=_strings(
                value.get("target_genes", ()),
                "candidate_element.target_genes",
                unique=True,
            ),
            state_ids=_strings(
                value.get("state_ids", ()),
                "candidate_element.state_ids",
                unique=True,
            ),
            features=features,
            annotations=_json_mapping(
                value.get("annotations", {}),
                "candidate_element.annotations",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CaseManifest:
    """Input contract for a reproducible case evaluation."""

    case_id: str
    subject_id: str
    context: ReferenceContext
    variants: tuple[VariantIdentity, ...]
    candidate_elements: tuple[CandidateElement, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)
    input_versions: Mapping[str, str] = field(default_factory=dict)
    requested_by: str = "unspecified"

    def __post_init__(self) -> None:
        require_non_empty(self.case_id, "case_id")
        require_non_empty(self.subject_id, "subject_id")
        if not self.variants:
            raise ValidationError("case must contain at least one variant")
        seen = set()
        for variant in self.variants:
            if variant.variant_id in seen:
                raise ValidationError(f"duplicate variant_id: {variant.variant_id}")
            seen.add(variant.variant_id)
        element_ids = [element.element_id for element in self.candidate_elements]
        if len(element_ids) != len(set(element_ids)):
            raise ValidationError("candidate element IDs must be unique")
        object.__setattr__(self, "metadata", _json_mapping(self.metadata, "metadata"))
        if not isinstance(self.input_versions, Mapping):
            raise ValidationError("input_versions must be an object")
        versions = {
            _string(key, "input_versions key"): _string(value, f"input_versions.{key}")
            for key, value in self.input_versions.items()
        }
        object.__setattr__(self, "input_versions", _json_mapping(versions, "input_versions"))

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> CaseManifest:
        allowed = frozenset(
            {
                "case_id",
                "subject_id",
                "context",
                "variants",
                "candidate_elements",
                "metadata",
                "input_versions",
                "requested_by",
            }
        )
        value = _strict_mapping(
            raw,
            label="case manifest",
            allowed=allowed,
            required=frozenset({"case_id", "subject_id", "context", "variants"}),
        )
        context_raw = value["context"]
        if not isinstance(context_raw, Mapping):
            raise ValidationError("case manifest context must be an object")
        context = ReferenceContext.from_dict(context_raw)
        variants = tuple(
            VariantIdentity.from_dict(item)
            for item in _sequence(value["variants"], "case manifest variants")
        )
        elements = tuple(
            CandidateElement.from_dict(item, context)
            for item in _sequence(
                value.get("candidate_elements", ()),
                "case manifest candidate_elements",
            )
        )
        versions_raw = value.get("input_versions", {})
        if not isinstance(versions_raw, Mapping):
            raise ValidationError("case manifest input_versions must be an object")
        return cls(
            case_id=_string(value["case_id"], "case manifest case_id"),
            subject_id=_string(value["subject_id"], "case manifest subject_id"),
            context=context,
            variants=variants,
            candidate_elements=elements,
            metadata=_json_mapping(value.get("metadata", {}), "case manifest metadata"),
            input_versions={
                _string(key, "case manifest input_versions key"): _string(
                    item,
                    f"case manifest input_versions.{key}",
                )
                for key, item in versions_raw.items()
            },
            requested_by=_string(
                value.get("requested_by", "unspecified"),
                "case manifest requested_by",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)

    @property
    def content_address(self) -> str:
        return content_hash(self.to_dict())


@dataclass(frozen=True, slots=True)
class EvidenceClaim:
    """An append-only claim about exactly one typed edge."""

    evidence_id: str
    edge_id: str
    source_id: str
    channel: str
    state: EvidenceState
    tier: EvidenceTier
    score: float | None
    confidence: float
    context: ReferenceContext
    summary: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    depends_on: tuple[str, ...] = ()
    produced_by: str = "deterministic_runtime"
    created_at: str = field(default_factory=lambda: utc_now().isoformat())
    supersedes: str | None = None

    def __post_init__(self) -> None:
        for name in ("evidence_id", "edge_id", "source_id", "channel", "summary"):
            object.__setattr__(self, name, require_non_empty(getattr(self, name), name))
        score = None if self.score is None else _number(self.score, "evidence score")
        confidence = _number(self.confidence, "evidence confidence")
        if score is not None and not 0.0 <= score <= 1.0:
            raise ValidationError("evidence score must be between 0 and 1")
        if not 0.0 <= confidence <= 1.0:
            raise ValidationError("evidence confidence must be between 0 and 1")
        object.__setattr__(self, "score", score)
        object.__setattr__(self, "confidence", confidence)
        object.__setattr__(self, "produced_by", require_non_empty(self.produced_by, "produced_by"))
        object.__setattr__(self, "created_at", require_non_empty(self.created_at, "created_at"))
        if self.supersedes is not None:
            object.__setattr__(
                self, "supersedes", require_non_empty(self.supersedes, "supersedes")
            )
        if self.supersedes == self.evidence_id:
            raise ValidationError("an evidence claim cannot supersede itself")
        if self.evidence_id in self.depends_on:
            raise ValidationError("an evidence claim cannot depend on itself")
        object.__setattr__(self, "payload", _json_mapping(self.payload, "evidence payload"))
        object.__setattr__(
            self,
            "depends_on",
            _strings(self.depends_on, "evidence depends_on", unique=True),
        )

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> EvidenceClaim:
        fields = frozenset(
            {
                "evidence_id",
                "edge_id",
                "source_id",
                "channel",
                "state",
                "tier",
                "score",
                "confidence",
                "context",
                "summary",
                "payload",
                "depends_on",
                "produced_by",
                "created_at",
                "supersedes",
            }
        )
        value = _strict_mapping(
            raw,
            label="evidence claim",
            allowed=fields,
            required=fields,
        )
        context_raw = value["context"]
        if not isinstance(context_raw, Mapping):
            raise ValidationError("evidence claim context must be an object")
        score_raw = value["score"]
        supersedes_raw = value["supersedes"]
        if supersedes_raw is not None and type(supersedes_raw) is not str:
            raise ValidationError("evidence claim supersedes must be a string or null")
        return cls(
            evidence_id=_string(value["evidence_id"], "evidence.evidence_id"),
            edge_id=_string(value["edge_id"], "evidence.edge_id"),
            source_id=_string(value["source_id"], "evidence.source_id"),
            channel=_string(value["channel"], "evidence.channel"),
            state=EvidenceState(_enum(EvidenceState, value["state"], "evidence.state")),
            tier=EvidenceTier(_enum(EvidenceTier, value["tier"], "evidence.tier")),
            score=None if score_raw is None else _number(score_raw, "evidence.score"),
            confidence=_number(value["confidence"], "evidence.confidence"),
            context=ReferenceContext.from_dict(context_raw, persisted=True),
            summary=_string(value["summary"], "evidence.summary"),
            payload=_json_mapping(value["payload"], "evidence.payload"),
            depends_on=_strings(value["depends_on"], "evidence.depends_on", unique=True),
            produced_by=_string(value["produced_by"], "evidence.produced_by"),
            created_at=_utc_timestamp(value["created_at"], "evidence.created_at"),
            supersedes=(
                None
                if supersedes_raw is None
                else _string(supersedes_raw, "evidence.supersedes")
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class HypothesisEdge:
    """One decomposed edge in a candidate causal path."""

    edge_id: str
    edge_type: EdgeType
    source_id: str
    target_id: str
    support: float
    uncertainty: float
    context_fit: float
    claim_ids: tuple[str, ...]
    support_level: SupportLevel
    alternatives: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("edge_id", "source_id", "target_id"):
            object.__setattr__(self, name, require_non_empty(getattr(self, name), name))
        if type(self.edge_type) is not EdgeType:
            raise ValidationError("edge_type must be an EdgeType")
        if type(self.support_level) is not SupportLevel:
            raise ValidationError("support_level must be a SupportLevel")
        for name in ("support", "uncertainty", "context_fit"):
            value = _number(getattr(self, name), f"edge {name}")
            if not 0.0 <= value <= 1.0:
                raise ValidationError(f"{name} must be between 0 and 1")
            object.__setattr__(self, name, value)
        if not self.claim_ids:
            raise ValidationError("each edge must reference at least one claim or abstention")
        object.__setattr__(
            self,
            "claim_ids",
            _strings(self.claim_ids, "edge claim_ids", non_empty=True, unique=True),
        )
        object.__setattr__(
            self,
            "alternatives",
            _strings(self.alternatives, "edge alternatives", unique=True),
        )

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> HypothesisEdge:
        fields = frozenset(
            {
                "edge_id",
                "edge_type",
                "source_id",
                "target_id",
                "support",
                "uncertainty",
                "context_fit",
                "claim_ids",
                "support_level",
                "alternatives",
            }
        )
        value = _strict_mapping(
            raw,
            label="hypothesis edge",
            allowed=fields,
            required=fields,
        )
        return cls(
            edge_id=_string(value["edge_id"], "edge.edge_id"),
            edge_type=EdgeType(_enum(EdgeType, value["edge_type"], "edge.edge_type")),
            source_id=_string(value["source_id"], "edge.source_id"),
            target_id=_string(value["target_id"], "edge.target_id"),
            support=_number(value["support"], "edge.support"),
            uncertainty=_number(value["uncertainty"], "edge.uncertainty"),
            context_fit=_number(value["context_fit"], "edge.context_fit"),
            claim_ids=_strings(
                value["claim_ids"],
                "edge.claim_ids",
                non_empty=True,
                unique=True,
            ),
            support_level=SupportLevel(
                _enum(SupportLevel, value["support_level"], "edge.support_level")
            ),
            alternatives=_strings(value["alternatives"], "edge.alternatives", unique=True),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class Hypothesis:
    """One candidate variant-element-gene-state path with explicit uncertainty."""

    hypothesis_id: str
    variant_id: str
    element_id: str
    gene_id: str
    state_id: str
    mechanism: str
    context: ReferenceContext
    edges: tuple[HypothesisEdge, ...]
    support: float
    uncertainty: float
    status: ResearchStatus = ResearchStatus.DRAFT
    missing_evidence: tuple[str, ...] = ()
    negative_evidence: tuple[str, ...] = ()
    alternatives: tuple[str, ...] = ()
    provenance: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in (
            "hypothesis_id",
            "variant_id",
            "element_id",
            "gene_id",
            "state_id",
            "mechanism",
        ):
            object.__setattr__(self, name, require_non_empty(getattr(self, name), name))
        if type(self.context) is not ReferenceContext:
            raise ValidationError("hypothesis context must be a ReferenceContext")
        if type(self.status) is not ResearchStatus:
            raise ValidationError("hypothesis status must be a ResearchStatus")
        if type(self.edges) is not tuple or any(
            type(edge) is not HypothesisEdge for edge in self.edges
        ):
            raise ValidationError("hypothesis edges must be typed HypothesisEdge objects")
        if not self.edges:
            raise ValidationError("a hypothesis must have at least one edge")
        for name in ("support", "uncertainty"):
            value = _number(getattr(self, name), f"hypothesis {name}")
            if not 0.0 <= value <= 1.0:
                raise ValidationError(f"{name} must be between 0 and 1")
            object.__setattr__(self, name, value)
        ensure_unique((edge.edge_id for edge in self.edges), "hypothesis edge_id")
        for name in ("missing_evidence", "negative_evidence", "alternatives", "provenance"):
            object.__setattr__(
                self,
                name,
                _strings(getattr(self, name), f"hypothesis {name}", unique=True),
            )

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> Hypothesis:
        fields = frozenset(
            {
                "hypothesis_id",
                "variant_id",
                "element_id",
                "gene_id",
                "state_id",
                "mechanism",
                "context",
                "edges",
                "support",
                "uncertainty",
                "status",
                "missing_evidence",
                "negative_evidence",
                "alternatives",
                "provenance",
            }
        )
        value = _strict_mapping(
            raw,
            label="hypothesis",
            allowed=fields,
            required=fields,
        )
        context_raw = value["context"]
        if not isinstance(context_raw, Mapping):
            raise ValidationError("hypothesis context must be an object")
        return cls(
            hypothesis_id=_string(value["hypothesis_id"], "hypothesis.hypothesis_id"),
            variant_id=_string(value["variant_id"], "hypothesis.variant_id"),
            element_id=_string(value["element_id"], "hypothesis.element_id"),
            gene_id=_string(value["gene_id"], "hypothesis.gene_id"),
            state_id=_string(value["state_id"], "hypothesis.state_id"),
            mechanism=_string(value["mechanism"], "hypothesis.mechanism"),
            context=ReferenceContext.from_dict(context_raw, persisted=True),
            edges=tuple(
                HypothesisEdge.from_dict(item)
                for item in _sequence(value["edges"], "hypothesis.edges")
            ),
            support=_number(value["support"], "hypothesis.support"),
            uncertainty=_number(value["uncertainty"], "hypothesis.uncertainty"),
            status=ResearchStatus(
                _enum(ResearchStatus, value["status"], "hypothesis.status")
            ),
            missing_evidence=_strings(
                value["missing_evidence"],
                "hypothesis.missing_evidence",
                unique=True,
            ),
            negative_evidence=_strings(
                value["negative_evidence"],
                "hypothesis.negative_evidence",
                unique=True,
            ),
            alternatives=_strings(
                value["alternatives"],
                "hypothesis.alternatives",
                unique=True,
            ),
            provenance=_strings(value["provenance"], "hypothesis.provenance", unique=True),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ExperimentOption:
    """A bounded validation option with explicit readouts and constraints."""

    option_id: str
    assay: AssayType
    tests_edges: tuple[str, ...]
    expected_information_gain: float
    feasibility: float
    cost_class: str
    required_context: tuple[str, ...]
    controls: tuple[str, ...]
    readouts: tuple[str, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "option_id", require_non_empty(self.option_id, "option_id"))
        if type(self.assay) is not AssayType:
            raise ValidationError("experiment assay must be an AssayType")
        object.__setattr__(self, "cost_class", require_non_empty(self.cost_class, "cost_class"))
        if not self.tests_edges:
            raise ValidationError("an experiment option must test at least one edge")
        for name in ("expected_information_gain", "feasibility"):
            value = _number(getattr(self, name), f"experiment {name}")
            if not 0.0 <= value <= 1.0:
                raise ValidationError(f"{name} must be between 0 and 1")
            object.__setattr__(self, name, value)
        object.__setattr__(
            self,
            "tests_edges",
            _strings(self.tests_edges, "experiment tests_edges", non_empty=True, unique=True),
        )
        for name in ("required_context", "controls", "readouts", "limitations"):
            object.__setattr__(
                self,
                name,
                _strings(getattr(self, name), f"experiment {name}", unique=True),
            )

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> ExperimentOption:
        fields = frozenset(
            {
                "option_id",
                "assay",
                "tests_edges",
                "expected_information_gain",
                "feasibility",
                "cost_class",
                "required_context",
                "controls",
                "readouts",
                "limitations",
            }
        )
        value = _strict_mapping(
            raw,
            label="experiment option",
            allowed=fields,
            required=fields,
        )
        return cls(
            option_id=_string(value["option_id"], "experiment.option_id"),
            assay=AssayType(_enum(AssayType, value["assay"], "experiment.assay")),
            tests_edges=_strings(
                value["tests_edges"],
                "experiment.tests_edges",
                non_empty=True,
                unique=True,
            ),
            expected_information_gain=_number(
                value["expected_information_gain"],
                "experiment.expected_information_gain",
            ),
            feasibility=_number(value["feasibility"], "experiment.feasibility"),
            cost_class=_string(value["cost_class"], "experiment.cost_class"),
            required_context=_strings(
                value["required_context"],
                "experiment.required_context",
                unique=True,
            ),
            controls=_strings(value["controls"], "experiment.controls", unique=True),
            readouts=_strings(value["readouts"], "experiment.readouts", unique=True),
            limitations=_strings(
                value["limitations"],
                "experiment.limitations",
                unique=True,
            ),
        )

    @property
    def priority(self) -> float:
        return round(self.expected_information_gain * self.feasibility, 6)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"priority": self.priority}


@dataclass(frozen=True, slots=True)
class ReviewDecision:
    """Human review record attached to a releaseable dossier."""

    review_id: str
    case_id: str
    reviewer: str
    state: ReviewState
    reviewed_hypothesis_ids: tuple[str, ...]
    rationale: str
    checked_claim_ids: tuple[str, ...]
    created_at: str = field(default_factory=lambda: utc_now().isoformat())

    def __post_init__(self) -> None:
        for name in ("review_id", "case_id", "reviewer", "rationale"):
            require_non_empty(getattr(self, name), name)
        if not self.reviewed_hypothesis_ids:
            raise ValidationError("review must name at least one hypothesis")
        object.__setattr__(
            self,
            "reviewed_hypothesis_ids",
            _strings(
                self.reviewed_hypothesis_ids,
                "review reviewed_hypothesis_ids",
                non_empty=True,
                unique=True,
            ),
        )
        object.__setattr__(
            self,
            "checked_claim_ids",
            _strings(self.checked_claim_ids, "review checked_claim_ids", unique=True),
        )

    @classmethod
    def from_dict(
        cls,
        raw: Mapping[str, Any],
        *,
        persisted: bool = False,
    ) -> ReviewDecision:
        """Rehydrate a review request from the public JSON contract."""

        fields = frozenset(
            {
                "review_id",
                "case_id",
                "reviewer",
                "state",
                "reviewed_hypothesis_ids",
                "rationale",
                "checked_claim_ids",
                "created_at",
            }
        )
        required = fields if persisted else fields - {"created_at"}
        value = _strict_mapping(
            raw,
            label="review decision",
            allowed=fields,
            required=required,
        )
        return cls(
            review_id=_string(value["review_id"], "review.review_id"),
            case_id=_string(value["case_id"], "review.case_id"),
            reviewer=_string(value["reviewer"], "review.reviewer"),
            state=ReviewState(_enum(ReviewState, value["state"], "review.state")),
            reviewed_hypothesis_ids=_strings(
                value["reviewed_hypothesis_ids"],
                "review.reviewed_hypothesis_ids",
                non_empty=True,
                unique=True,
            ),
            rationale=_string(value["rationale"], "review.rationale"),
            checked_claim_ids=_strings(
                value["checked_claim_ids"],
                "review.checked_claim_ids",
                unique=True,
            ),
            created_at=(
                _utc_timestamp(value["created_at"], "review.created_at")
                if "created_at" in value
                else utc_now().isoformat()
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class Dossier:
    """Replayable case snapshot suitable for local review and research release."""

    dossier_id: str
    case_id: str
    run_id: str
    created_at: str
    input_address: str
    hypotheses: tuple[Hypothesis, ...]
    evidence: tuple[EvidenceClaim, ...]
    experiments: tuple[ExperimentOption, ...]
    review: ReviewDecision | None
    research_use_only: bool
    policy_version: str
    event_head: str
    content_address: str
    status: ResearchStatus
    warnings: tuple[str, ...] = ()
    source_receipts: tuple[Mapping[str, Any], ...] = ()
    source_bundle_addresses: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in (
            "dossier_id",
            "case_id",
            "run_id",
            "created_at",
            "input_address",
            "policy_version",
            "event_head",
            "content_address",
        ):
            require_non_empty(getattr(self, name), name)
        if type(self.research_use_only) is not bool:
            raise ValidationError("research_use_only must be a boolean")

        object.__setattr__(self, "warnings", _strings(self.warnings, "dossier warnings"))
        frozen_receipts: list[Mapping[str, Any]] = []
        for index, receipt in enumerate(self.source_receipts):
            frozen_receipts.append(
                _json_mapping(receipt, f"dossier source_receipts[{index}]")
            )
        object.__setattr__(self, "source_receipts", tuple(frozen_receipts))
        object.__setattr__(
            self,
            "source_bundle_addresses",
            _strings(
                self.source_bundle_addresses,
                "dossier source_bundle_addresses",
                unique=True,
            ),
        )

    def _validate_structure(self) -> None:
        """Validate the closed identity graph of a persisted dossier."""

        hypothesis_ids = tuple(item.hypothesis_id for item in self.hypotheses)
        evidence_ids = tuple(item.evidence_id for item in self.evidence)
        option_ids = tuple(item.option_id for item in self.experiments)
        ensure_unique(hypothesis_ids, "dossier hypothesis_id")
        ensure_unique(evidence_ids, "dossier evidence_id")
        ensure_unique(option_ids, "dossier option_id")

        edges = tuple(edge for hypothesis in self.hypotheses for edge in hypothesis.edges)
        edge_ids = tuple(edge.edge_id for edge in edges)
        edges_by_id: dict[str, HypothesisEdge] = {}
        for edge in edges:
            previous = edges_by_id.get(edge.edge_id)
            if previous is not None and canonical_bytes(previous.to_dict()) != canonical_bytes(
                edge.to_dict()
            ):
                raise ValidationError(
                    f"edge {edge.edge_id} has conflicting definitions across hypotheses"
                )
            edges_by_id[edge.edge_id] = edge
        evidence_by_id = {item.evidence_id: item for item in self.evidence}
        for edge in edges_by_id.values():
            for claim_id in edge.claim_ids:
                claim = evidence_by_id.get(claim_id)
                if claim is None:
                    raise ValidationError(
                        f"edge {edge.edge_id} references unknown evidence claim {claim_id}"
                    )
                if claim.edge_id != edge.edge_id:
                    raise ValidationError(
                        f"evidence claim {claim_id} is bound to {claim.edge_id}, not {edge.edge_id}"
                    )

        evidence_positions = {
            claim.evidence_id: index for index, claim in enumerate(self.evidence)
        }
        for index, claim in enumerate(self.evidence):
            for dependency in claim.depends_on:
                dependency_index = evidence_positions.get(dependency)
                if dependency_index is None:
                    _content_address(
                        dependency,
                        f"evidence {claim.evidence_id} dependency",
                    )
                elif dependency_index >= index:
                    raise ValidationError(
                        f"evidence claim {claim.evidence_id} has a forward or cyclic dependency"
                    )
            if claim.supersedes is not None:
                superseded_index = evidence_positions.get(claim.supersedes)
                if superseded_index is None:
                    raise ValidationError(
                        f"evidence claim {claim.evidence_id} supersedes unknown evidence "
                        f"{claim.supersedes}"
                    )
                if superseded_index >= index:
                    raise ValidationError(
                        f"evidence claim {claim.evidence_id} must supersede earlier evidence"
                    )

        missing_states = {
            EvidenceState.ABSENT,
            EvidenceState.UNSUPPORTED,
            EvidenceState.OUT_OF_DOMAIN,
            EvidenceState.ABSTAINED,
        }
        negative_states = {
            EvidenceState.MEASURED_NEGATIVE,
            EvidenceState.CONTRADICTORY,
        }
        for hypothesis in self.hypotheses:
            hypothesis_claim_ids = {
                claim_id for edge in hypothesis.edges for claim_id in edge.claim_ids
            }
            for claim_id in hypothesis.missing_evidence:
                claim = evidence_by_id.get(claim_id)
                if claim is None or claim_id not in hypothesis_claim_ids:
                    raise ValidationError(
                        f"hypothesis {hypothesis.hypothesis_id} has unknown missing evidence "
                        f"{claim_id}"
                    )
                if claim.state not in missing_states:
                    raise ValidationError(
                        f"hypothesis {hypothesis.hypothesis_id} classifies non-missing claim "
                        f"{claim_id} as missing"
                    )
            for claim_id in hypothesis.negative_evidence:
                claim = evidence_by_id.get(claim_id)
                if claim is None or claim_id not in hypothesis_claim_ids:
                    raise ValidationError(
                        f"hypothesis {hypothesis.hypothesis_id} has unknown negative evidence "
                        f"{claim_id}"
                    )
                if claim.state not in negative_states:
                    raise ValidationError(
                        f"hypothesis {hypothesis.hypothesis_id} classifies non-negative claim "
                        f"{claim_id} as negative"
                    )
            self._validate_hypothesis_path(hypothesis)

        known_edges = set(edge_ids)
        for experiment in self.experiments:
            missing_edges = set(experiment.tests_edges) - known_edges
            if missing_edges:
                raise ValidationError(
                    f"experiment {experiment.option_id} references unknown edges: "
                    f"{sorted(missing_edges)}"
                )

        if self.review is not None:
            if self.review.case_id != self.case_id:
                raise ValidationError("review case_id does not match dossier case_id")
            unknown_hypotheses = set(self.review.reviewed_hypothesis_ids) - set(hypothesis_ids)
            if unknown_hypotheses:
                raise ValidationError(
                    "review references unknown hypotheses: "
                    f"{sorted(unknown_hypotheses)}"
                )
            unknown_claims = set(self.review.checked_claim_ids) - set(evidence_ids)
            if unknown_claims:
                raise ValidationError(
                    f"review references unknown evidence claims: {sorted(unknown_claims)}"
                )

    @staticmethod
    def _validate_hypothesis_path(hypothesis: Hypothesis) -> None:
        if (
            hypothesis.element_id == "unresolved"
            and hypothesis.gene_id == "unresolved_gene"
            and hypothesis.state_id == "unresolved_state"
        ):
            if (
                len(hypothesis.edges) != 1
                or hypothesis.edges[0].edge_type != EdgeType.CAUSAL_PATH
                or hypothesis.edges[0].source_id != hypothesis.variant_id
                or hypothesis.edges[0].target_id != "unresolved"
                or not hypothesis.mechanism.startswith("abstained:")
                or hypothesis.support != 0.0
                or hypothesis.uncertainty != 1.0
            ):
                raise ValidationError(
                    f"hypothesis {hypothesis.hypothesis_id} has an invalid abstention path"
                )
            return

        required_links = (
            (
                EdgeType.VARIANT_TO_ELEMENT,
                hypothesis.variant_id,
                hypothesis.element_id,
                "variant-to-element",
            ),
            (
                EdgeType.ELEMENT_TO_GENE,
                hypothesis.element_id,
                hypothesis.gene_id,
                "element-to-gene",
            ),
            (
                EdgeType.GENE_TO_STATE,
                hypothesis.gene_id,
                hypothesis.state_id,
                "gene-to-state",
            ),
            (
                EdgeType.CAUSAL_PATH,
                hypothesis.variant_id,
                hypothesis.state_id,
                "causal-path",
            ),
        )
        for edge_type, source_id, target_id, label in required_links:
            if not any(
                edge.edge_type == edge_type
                and edge.source_id == source_id
                and edge.target_id == target_id
                for edge in hypothesis.edges
            ):
                raise ValidationError(
                    f"hypothesis {hypothesis.hypothesis_id} is missing its {label} identity edge"
                )

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> Dossier:
        """Rehydrate an immutable stored dossier for a follow-up review."""

        fields = frozenset(
            {
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
        )
        value = _strict_mapping(
            raw,
            label="dossier",
            allowed=fields,
            required=fields,
        )
        review_raw = value["review"]
        if review_raw is not None and not isinstance(review_raw, Mapping):
            raise ValidationError("dossier review must be an object or null")
        receipts: list[Mapping[str, Any]] = []
        for index, item in enumerate(
            _sequence(value["source_receipts"], "dossier.source_receipts")
        ):
            receipts.append(_json_mapping(item, f"dossier.source_receipts[{index}]"))
        dossier = cls(
            dossier_id=_string(value["dossier_id"], "dossier.dossier_id"),
            case_id=_string(value["case_id"], "dossier.case_id"),
            run_id=_string(value["run_id"], "dossier.run_id"),
            created_at=_utc_timestamp(value["created_at"], "dossier.created_at"),
            input_address=_sha256_address(value["input_address"], "dossier.input_address"),
            hypotheses=tuple(
                Hypothesis.from_dict(item)
                for item in _sequence(value["hypotheses"], "dossier.hypotheses")
            ),
            evidence=tuple(
                EvidenceClaim.from_dict(item)
                for item in _sequence(value["evidence"], "dossier.evidence")
            ),
            experiments=tuple(
                ExperimentOption.from_dict(item)
                for item in _sequence(value["experiments"], "dossier.experiments")
            ),
            review=(
                ReviewDecision.from_dict(review_raw, persisted=True)
                if review_raw is not None
                else None
            ),
            research_use_only=_boolean(
                value["research_use_only"],
                "dossier.research_use_only",
            ),
            policy_version=_string(value["policy_version"], "dossier.policy_version"),
            event_head=_sha256_address(value["event_head"], "dossier.event_head"),
            content_address=_sha256_address(
                value["content_address"],
                "dossier.content_address",
            ),
            status=ResearchStatus(_enum(ResearchStatus, value["status"], "dossier.status")),
            warnings=_strings(value["warnings"], "dossier.warnings"),
            source_receipts=tuple(receipts),
            source_bundle_addresses=tuple(
                _sha256_address(item, f"dossier.source_bundle_addresses[{index}]")
                for index, item in enumerate(
                    _sequence(
                        value["source_bundle_addresses"],
                        "dossier.source_bundle_addresses",
                    )
                )
            ),
        )
        dossier._validate_structure()
        _require_exact_roundtrip(value, dossier, "dossier")
        body = {
            key: item
            for key, item in dossier.to_dict().items()
            if key != "content_address"
        }
        if dossier.content_address != content_hash(body):
            raise ValidationError("dossier content_address does not match its canonical payload")
        return dossier

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)

    @property
    def is_releasable(self) -> bool:
        try:
            eligible = (
                type(self) is Dossier
                and self.status is ResearchStatus.RELEASED_RESEARCH
                and type(self.research_use_only) is bool
                and self.research_use_only
                and type(self.review) is ReviewDecision
                and self.review.state is ReviewState.ACCEPTED
            )
            if not eligible:
                return False
            self._validate_structure()
            review = self.review
            if type(review) is not ReviewDecision:  # pragma: no cover - narrowed above
                return False
            hypothesis_ids = tuple(item.hypothesis_id for item in self.hypotheses)
            claim_ids = tuple(item.evidence_id for item in self.evidence)
            if (
                type(review.reviewed_hypothesis_ids) is not tuple
                or type(review.checked_claim_ids) is not tuple
                or len(review.reviewed_hypothesis_ids) != len(hypothesis_ids)
                or len(review.checked_claim_ids) != len(claim_ids)
                or set(review.reviewed_hypothesis_ids) != set(hypothesis_ids)
                or set(review.checked_claim_ids) != set(claim_ids)
            ):
                return False
            payload = self.to_dict()
            supplied_address = payload.pop("content_address", None)
            return (
                type(supplied_address) is str
                and supplied_address == content_hash(payload)
            )
        except Exception:  # noqa: BLE001 - this summary property must fail closed
            return False


def enum_values(enum_type: type[ValueEnum]) -> list[str]:
    """Expose allowed values for schema and client generation."""

    return [item.value for item in enum_type]


def ensure_unique(values: Iterable[str], label: str) -> None:
    """Validate uniqueness in a collection while preserving caller ordering."""

    values_list = list(values)
    if len(values_list) != len(set(values_list)):
        raise ValidationError(f"{label} values must be unique")
