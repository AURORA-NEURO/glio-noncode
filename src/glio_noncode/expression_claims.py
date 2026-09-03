"""Bridge matched RNA consequences into native element-to-gene claims.

The expression evidence layer intentionally emits a sample-free consequence
object, while the hypothesis runtime consumes :class:`EvidenceClaim` objects
attached to deterministic edge identifiers.  This module is the narrow bridge
between those contracts.  It does not inspect raw expression or allelic-count
inputs and it never guesses an element when more than one target matches.

Scores are bounded evidence-strength summaries, not probabilities.  Directional
strength uses the larger of a robust-expression effect and an allele-specific
effect, keeping the two correlated RNA measurements in one evidence channel so
the native aggregator cannot double count them.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from itertools import islice
from typing import Any

from .errors import ValidationError
from .expression_evidence import RNAConsequenceEvidence, RNAEvidenceState
from .models import EdgeType, EvidenceClaim, EvidenceState, EvidenceTier, ReferenceContext
from .serialization import canonical_json, content_hash

SCHEMA_VERSION = "1.0.0"
RNA_CONSEQUENCE_CHANNEL = "matched_rna_consequence"
PRODUCED_BY = "deterministic_rna_claim_bridge"

# EvidenceClaim includes an observational timestamp for append-only stores.  A
# pure bridge has no observation time, so a stable sentinel prevents wall-clock
# time from changing otherwise identical scientific content.
DETERMINISTIC_CREATED_AT = "1970-01-01T00:00:00+00:00"

# Keep direct claim matching at the same bounded scale as case-workflow RNA
# execution.  The limit applies independently to consequences and targets.
MAX_RNA_CLAIM_BATCH_ITEMS = 10_000

_REASON_CODE_RE = re.compile(r"[a-z][a-z0-9_]{0,127}\Z")
_ADDRESS_DIGEST_RE = re.compile(r"[0-9a-f]{64}\Z")
_FORBIDDEN_PUBLIC_KEYS = frozenset(
    {
        "cohort_values",
        "observations",
        "patient_id",
        "sample",
        "sample_id",
        "sample_key",
        "subject_id",
        "target_value",
    }
)

_STATE_MAP: Mapping[RNAEvidenceState, EvidenceState] = {
    RNAEvidenceState.SUPPORTED: EvidenceState.SUPPORTED,
    RNAEvidenceState.CONTRADICTORY: EvidenceState.CONTRADICTORY,
    RNAEvidenceState.MEASURED_NEGATIVE: EvidenceState.MEASURED_NEGATIVE,
    RNAEvidenceState.OUT_OF_DOMAIN: EvidenceState.OUT_OF_DOMAIN,
    RNAEvidenceState.ABSTAINED: EvidenceState.ABSTAINED,
}


def _text(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValidationError(f"{field_name} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValidationError(f"{field_name} must not be empty")
    if len(normalized) > 512 or any(ord(character) < 32 for character in normalized):
        raise ValidationError(f"{field_name} contains invalid characters")
    return normalized


def _typed_content_address(value: object, *, prefix: str, field_name: str) -> str:
    """Require one exact, lower-case content address in the expected namespace."""

    expected_prefix = f"{prefix}:"
    if (
        type(value) is not str
        or not value.startswith(expected_prefix)
        or _ADDRESS_DIGEST_RE.fullmatch(value[len(expected_prefix) :]) is None
    ):
        raise ValidationError(f"{field_name} must be a canonical {prefix} content address")
    return value


def _retained_owner_address(value: object) -> str | None:
    if value is None:
        return None
    return _typed_content_address(
        value,
        prefix="sha256",
        field_name="retained_owner_address",
    )


def _finite(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(f"{field_name} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValidationError(f"{field_name} must be finite")
    return result


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{label} must be a mapping")
    return value


def _sequence(value: object, label: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValidationError(f"{label} must be a sequence")
    return value


def _bounded_batch_rows(values: Iterable[Any], label: str) -> tuple[Any, ...]:
    if isinstance(values, (str, bytes, bytearray, Mapping)):
        raise ValidationError(f"{label} must be an iterable of objects")
    try:
        rows = tuple(islice(iter(values), MAX_RNA_CLAIM_BATCH_ITEMS + 1))
    except TypeError as error:
        raise ValidationError(f"{label} must be iterable") from error
    if len(rows) > MAX_RNA_CLAIM_BATCH_ITEMS:
        raise ValidationError(f"{label} exceeds the maximum of {MAX_RNA_CLAIM_BATCH_ITEMS} items")
    return rows


def _json_mapping(text: str, label: str) -> Mapping[str, Any]:
    try:
        value = json.loads(text)
    except (TypeError, json.JSONDecodeError) as error:
        raise ValidationError(f"{label} must be valid JSON") from error
    return _mapping(value, label)


def _strict_keys(
    raw: Mapping[str, Any],
    *,
    required: frozenset[str],
    optional: frozenset[str] = frozenset(),
    label: str,
) -> None:
    keys = frozenset(str(key) for key in raw)
    missing = required - keys
    extra = keys - required - optional
    if missing:
        raise ValidationError(f"{label} is missing fields: {', '.join(sorted(missing))}")
    if extra:
        raise ValidationError(f"{label} contains unknown fields: {', '.join(sorted(extra))}")


def _verify_address(raw: Mapping[str, Any], actual: str, label: str) -> None:
    declared = raw.get("content_address")
    if declared is not None and declared != actual:
        raise ValidationError(f"{label} content_address does not match canonical content")


def _assert_sample_free(value: object, *, path: str = "payload") -> None:
    if isinstance(value, Mapping):
        for raw_key, item in value.items():
            key = str(raw_key).lower()
            if key in _FORBIDDEN_PUBLIC_KEYS or key.startswith("sample_"):
                raise ValidationError(f"{path} contains private field {raw_key!r}")
            _assert_sample_free(item, path=f"{path}.{raw_key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _assert_sample_free(item, path=f"{path}[{index}]")


def element_gene_edge_id(element_id: str, gene_id: str) -> str:
    """Return the exact edge identifier used by ``HypothesisBuilder``."""

    source = _text(element_id, "element_id")
    target = _text(gene_id, "gene_id")
    digest = content_hash(
        {"source": source, "target": target, "type": EdgeType.ELEMENT_TO_GENE.value}
    ).split(":", 1)[1]
    return f"edge-{digest[:20]}"


@dataclass(frozen=True, slots=True)
class RNAElementGeneTarget:
    """One explicit variant/element/gene/context destination for RNA evidence."""

    variant_id: str
    element_id: str
    gene_id: str
    context: ReferenceContext

    def __post_init__(self) -> None:
        for field_name in ("variant_id", "element_id", "gene_id"):
            object.__setattr__(self, field_name, _text(getattr(self, field_name), field_name))
        if not isinstance(self.context, ReferenceContext):
            raise ValidationError("context must be a ReferenceContext")

    @property
    def match_key(self) -> tuple[str, str, str]:
        return (self.variant_id, self.gene_id, self.context.key)

    @property
    def edge_id(self) -> str:
        return element_gene_edge_id(self.element_id, self.gene_id)

    def _payload(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "variant_id": self.variant_id,
            "element_id": self.element_id,
            "gene_id": self.gene_id,
            "context": self.context.to_dict(),
            "context_key": self.context.key,
            "edge_id": self.edge_id,
        }

    @property
    def content_address(self) -> str:
        return content_hash(self._payload(), prefix="rna-claim-target")

    def to_dict(self) -> dict[str, Any]:
        return self._payload() | {"content_address": self.content_address}

    public_projection = to_dict
    to_public_dict = to_dict

    def to_json(self) -> str:
        return canonical_json(self.to_dict())

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> RNAElementGeneTarget:
        value = _mapping(raw, "RNA element-gene target")
        _strict_keys(
            value,
            required=frozenset(
                {
                    "schema_version",
                    "variant_id",
                    "element_id",
                    "gene_id",
                    "context",
                    "context_key",
                    "edge_id",
                }
            ),
            optional=frozenset({"content_address"}),
            label="RNA element-gene target",
        )
        if value.get("schema_version") != SCHEMA_VERSION:
            raise ValidationError("unsupported RNA element-gene target schema_version")
        result = cls(
            variant_id=value.get("variant_id"),
            element_id=value.get("element_id"),
            gene_id=value.get("gene_id"),
            context=ReferenceContext.from_dict(_mapping(value.get("context"), "context")),
        )
        if value.get("context_key") != result.context.key:
            raise ValidationError("target context_key disagrees with context")
        if value.get("edge_id") != result.edge_id:
            raise ValidationError("target edge_id is not the deterministic element-to-gene edge")
        _verify_address(value, result.content_address, "RNA element-gene target")
        return result

    @classmethod
    def from_json(cls, text: str) -> RNAElementGeneTarget:
        return cls.from_mapping(_json_mapping(text, "RNA element-gene target"))


@dataclass(frozen=True, slots=True)
class RNAClaimPolicy:
    """Explicit conservative normalization limits for bridge-only strengths."""

    expression_saturation_z: float = 7.0
    allelic_saturation_log2_ratio: float = 2.0
    allelic_q_reference: float = 0.05
    max_directional_score: float = 0.80
    measured_negative_score: float = 0.45
    single_component_confidence: float = 0.55
    multi_component_confidence: float = 0.68

    def __post_init__(self) -> None:
        for field_name in ("expression_saturation_z", "allelic_saturation_log2_ratio"):
            value = _finite(getattr(self, field_name), field_name)
            if value <= 0.0:
                raise ValidationError(f"{field_name} must be positive")
            object.__setattr__(self, field_name, value)
        for field_name in (
            "allelic_q_reference",
            "max_directional_score",
            "measured_negative_score",
            "single_component_confidence",
            "multi_component_confidence",
        ):
            value = _finite(getattr(self, field_name), field_name)
            if not 0.0 < value <= 1.0:
                raise ValidationError(f"{field_name} must be greater than 0 and at most 1")
            object.__setattr__(self, field_name, value)
        if self.multi_component_confidence < self.single_component_confidence:
            raise ValidationError(
                "multi_component_confidence must not be below single_component_confidence"
            )

    def to_dict(self) -> dict[str, float | str]:
        return {
            "schema_version": SCHEMA_VERSION,
            "expression_saturation_z": self.expression_saturation_z,
            "allelic_saturation_log2_ratio": self.allelic_saturation_log2_ratio,
            "allelic_q_reference": self.allelic_q_reference,
            "max_directional_score": self.max_directional_score,
            "measured_negative_score": self.measured_negative_score,
            "single_component_confidence": self.single_component_confidence,
            "multi_component_confidence": self.multi_component_confidence,
        }


DEFAULT_RNA_CLAIM_POLICY = RNAClaimPolicy()


@dataclass(frozen=True, slots=True)
class RNAClaimDerivation:
    """Auditable normalization result used to populate a native claim."""

    score: float | None
    confidence: float
    expression_strength: float | None
    allelic_strength: float | None
    component_count: int
    rationale: str

    def __post_init__(self) -> None:
        for field_name in ("score", "expression_strength", "allelic_strength"):
            value = getattr(self, field_name)
            if value is not None:
                normalized = _finite(value, field_name)
                if not 0.0 <= normalized <= 1.0:
                    raise ValidationError(f"{field_name} must be between 0 and 1")
                object.__setattr__(self, field_name, normalized)
        confidence = _finite(self.confidence, "confidence")
        if not 0.0 <= confidence <= 1.0:
            raise ValidationError("confidence must be between 0 and 1")
        object.__setattr__(self, "confidence", confidence)
        if isinstance(self.component_count, bool) or self.component_count not in (0, 1, 2):
            raise ValidationError("component_count must be 0, 1, or 2")
        object.__setattr__(self, "rationale", _text(self.rationale, "rationale"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "confidence": self.confidence,
            "expression_strength": self.expression_strength,
            "allelic_strength": self.allelic_strength,
            "component_count": self.component_count,
            "rationale": self.rationale,
        }


def validate_rna_consequence(evidence: object) -> RNAConsequenceEvidence:
    """Validate one exact canonical consequence before claim or replay use."""

    if type(evidence) is not RNAConsequenceEvidence:
        raise ValidationError("evidence must be an exact RNAConsequenceEvidence")
    try:
        raw = evidence.to_dict()
        canonical = RNAConsequenceEvidence.from_mapping(raw)
    except Exception as error:  # noqa: BLE001 - forged frozen objects fail closed
        raise ValidationError("RNA consequence evidence is not canonical") from error
    if canonical != evidence or canonical.to_dict() != raw:
        raise ValidationError("RNA consequence evidence does not round-trip exactly")
    if evidence.state not in _STATE_MAP:
        raise ValidationError(f"unsupported RNA evidence state: {evidence.state!r}")
    for code in evidence.reason_codes:
        if type(code) is not str or not _REASON_CODE_RE.fullmatch(code):
            raise ValidationError("RNA reason_codes must be stable lower-case opaque codes")

    expression_values = (
        evidence.expression_state,
        evidence.expression_direction,
        evidence.expression_robust_z,
        evidence.expression_result_address,
    )
    if any(value is not None for value in expression_values):
        if evidence.expression_state is None or evidence.expression_result_address is None:
            raise ValidationError("partial expression consequence cannot become a claim")

    allelic_values = (
        evidence.allelic_state,
        evidence.allelic_direction,
        evidence.allelic_log2_ratio,
        evidence.allelic_q_value,
        evidence.allelic_result_address,
    )
    if any(value is not None for value in allelic_values):
        if evidence.allelic_state is None or evidence.allelic_result_address is None:
            raise ValidationError("partial allelic consequence cannot become a claim")

    if (
        evidence.state
        in (
            RNAEvidenceState.SUPPORTED,
            RNAEvidenceState.CONTRADICTORY,
            RNAEvidenceState.MEASURED_NEGATIVE,
        )
        and evidence.expression_result_address is None
        and evidence.allelic_result_address is None
    ):
        raise ValidationError(f"{evidence.state.value} consequence has no measured RNA component")

    _typed_content_address(
        evidence.prediction_address,
        prefix="regulatory-effect-prediction",
        field_name="prediction_address",
    )
    if evidence.expression_result_address is not None:
        _typed_content_address(
            evidence.expression_result_address,
            prefix="expression-outlier",
            field_name="expression_result_address",
        )
    if evidence.allelic_result_address is not None:
        _typed_content_address(
            evidence.allelic_result_address,
            prefix="allelic-imbalance",
            field_name="allelic_result_address",
        )
    return evidence


def matches_rna_consequence(evidence: RNAConsequenceEvidence, target: RNAElementGeneTarget) -> bool:
    """Return whether all three scientific scope keys match exactly."""

    validate_rna_consequence(evidence)
    if not isinstance(target, RNAElementGeneTarget):
        raise ValidationError("target must be RNAElementGeneTarget")
    return (
        evidence.variant_id,
        evidence.feature_id,
        evidence.context_key,
    ) == target.match_key


def _derive_strength(
    evidence: RNAConsequenceEvidence, policy: RNAClaimPolicy
) -> RNAClaimDerivation:
    expression_strength = None
    if evidence.expression_robust_z is not None:
        expression_strength = round(
            min(1.0, abs(evidence.expression_robust_z) / policy.expression_saturation_z),
            6,
        )

    allelic_strength = None
    if evidence.allelic_log2_ratio is not None:
        effect = min(
            1.0,
            abs(evidence.allelic_log2_ratio) / policy.allelic_saturation_log2_ratio,
        )
        # 1 / (1 + q/reference) is bounded, monotone, and still assigns only
        # half weight at the declared reference q-value.
        significance = (
            0.5
            if evidence.allelic_q_value is None
            else 1.0 / (1.0 + evidence.allelic_q_value / policy.allelic_q_reference)
        )
        allelic_strength = round(math.sqrt(effect * significance), 6)

    component_count = sum(
        address is not None
        for address in (evidence.expression_result_address, evidence.allelic_result_address)
    )
    state = evidence.state
    if state in (RNAEvidenceState.OUT_OF_DOMAIN, RNAEvidenceState.ABSTAINED):
        return RNAClaimDerivation(
            score=None,
            confidence=0.0,
            expression_strength=expression_strength,
            allelic_strength=allelic_strength,
            component_count=component_count,
            rationale=("No numeric support is assigned to out-of-domain or abstained evidence."),
        )

    confidence = (
        policy.multi_component_confidence
        if component_count == 2
        else policy.single_component_confidence
    )
    if state is RNAEvidenceState.MEASURED_NEGATIVE:
        return RNAClaimDerivation(
            score=round(policy.measured_negative_score, 6),
            confidence=round(confidence, 6),
            expression_strength=expression_strength,
            allelic_strength=allelic_strength,
            component_count=component_count,
            rationale=(
                "Measured-negative strength is a fixed conservative bound; effect magnitude "
                "is not reinterpreted as positive support."
            ),
        )

    strengths = tuple(
        value for value in (expression_strength, allelic_strength) if value is not None
    )
    if not strengths or max(strengths) <= 0.0:
        raise ValidationError(f"{state.value} consequence has no non-zero directional RNA strength")
    score = round(policy.max_directional_score * max(strengths), 6)
    return RNAClaimDerivation(
        score=score,
        confidence=round(confidence, 6),
        expression_strength=expression_strength,
        allelic_strength=allelic_strength,
        component_count=component_count,
        rationale=(
            "Directional score is max(expression, allelic) times the configured cap; "
            "correlated RNA components are not summed."
        ),
    )


def _mismatch_dimensions(
    evidence: RNAConsequenceEvidence, target: RNAElementGeneTarget
) -> tuple[str, ...]:
    mismatches: list[str] = []
    if evidence.variant_id != target.variant_id:
        mismatches.append("variant_id")
    if evidence.feature_id != target.gene_id:
        mismatches.append("feature_id/gene_id")
    if evidence.context_key != target.context.key:
        mismatches.append("context_key")
    return tuple(mismatches)


def rna_consequence_to_claim(
    evidence: RNAConsequenceEvidence,
    target: RNAElementGeneTarget,
    *,
    policy: RNAClaimPolicy = DEFAULT_RNA_CLAIM_POLICY,
    retained_owner_address: str | None = None,
) -> EvidenceClaim:
    """Build one deterministic native claim after exact three-key matching."""

    owner_address = _retained_owner_address(retained_owner_address)
    validate_rna_consequence(evidence)
    if not isinstance(target, RNAElementGeneTarget):
        raise ValidationError("target must be RNAElementGeneTarget")
    if not isinstance(policy, RNAClaimPolicy):
        raise ValidationError("policy must be RNAClaimPolicy")
    mismatches = _mismatch_dimensions(evidence, target)
    if mismatches:
        raise ValidationError("RNA consequence does not match target: " + ", ".join(mismatches))

    derivation = _derive_strength(evidence, policy)
    native_state = _STATE_MAP[evidence.state]
    source_addresses = tuple(
        sorted(
            address
            for address in (
                evidence.prediction_address,
                evidence.expression_result_address,
                evidence.allelic_result_address,
            )
            if address is not None
        )
    )
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "target": {
            "variant_id": target.variant_id,
            "element_id": target.element_id,
            "gene_id": target.gene_id,
            "context_key": target.context.key,
            "target_address": target.content_address,
        },
        "rna_consequence": {
            "content_address": evidence.content_address,
            "prediction_id": evidence.prediction_id,
            "prediction_address": evidence.prediction_address,
            "variant_id": evidence.variant_id,
            "feature_id": evidence.feature_id,
            "context_key": evidence.context_key,
            "predicted_direction": evidence.predicted_direction.value,
            "state": evidence.state.value,
            "expression_state": (
                evidence.expression_state.value if evidence.expression_state is not None else None
            ),
            "expression_direction": (
                evidence.expression_direction.value
                if evidence.expression_direction is not None
                else None
            ),
            "expression_robust_z": evidence.expression_robust_z,
            "expression_result_address": evidence.expression_result_address,
            "allelic_state": (
                evidence.allelic_state.value if evidence.allelic_state is not None else None
            ),
            "allelic_direction": (
                evidence.allelic_direction.value if evidence.allelic_direction is not None else None
            ),
            "allelic_log2_ratio": evidence.allelic_log2_ratio,
            "allelic_q_value": evidence.allelic_q_value,
            "allelic_result_address": evidence.allelic_result_address,
            "reason_codes": list(evidence.reason_codes),
        },
        "derivation": derivation.to_dict(),
        "policy": policy.to_dict(),
        "source_addresses": list(source_addresses),
        "privacy": {
            "identifiers_excluded": True,
            "raw_measurements_excluded": True,
            "cohort_vectors_excluded": True,
        },
    }
    if owner_address is not None:
        payload["retained_owner_address"] = owner_address
    _assert_sample_free(payload)
    action = {
        RNAEvidenceState.SUPPORTED: "supports",
        RNAEvidenceState.CONTRADICTORY: "contradicts",
        RNAEvidenceState.MEASURED_NEGATIVE: "is measured-negative for",
        RNAEvidenceState.OUT_OF_DOMAIN: "is out-of-domain for",
        RNAEvidenceState.ABSTAINED: "abstains for",
    }[evidence.state]
    claim = EvidenceClaim(
        evidence_id="pending-rna-claim-address",
        edge_id=target.edge_id,
        source_id=f"rna-consequence:{evidence.prediction_id}",
        channel=RNA_CONSEQUENCE_CHANNEL,
        state=native_state,
        tier=EvidenceTier.COMPUTED,
        score=derivation.score,
        confidence=derivation.confidence,
        context=target.context,
        summary=(
            f"Matched RNA consequence {action} the {target.element_id} to "
            f"{target.gene_id} regulatory link for {target.variant_id}."
        ),
        payload=payload,
        depends_on=(owner_address,) if owner_address is not None else source_addresses,
        produced_by=PRODUCED_BY,
        created_at=DETERMINISTIC_CREATED_AT,
    )
    digest = content_hash(_claim_identity_payload(claim)).split(":", 1)[1]
    return replace(claim, evidence_id=f"ev-rna-{digest[:20]}")


def _bridge_claim_consequence_address(claim: EvidenceClaim) -> str:
    payload = _mapping(claim.payload, "claim payload")
    consequence = _mapping(payload.get("rna_consequence"), "rna_consequence")
    return _text(consequence.get("content_address"), "rna consequence content_address")


def _bridge_claim_target_address(claim: EvidenceClaim) -> str:
    payload = _mapping(claim.payload, "claim payload")
    target = _mapping(payload.get("target"), "target")
    return _text(target.get("target_address"), "target_address")


def _claim_identity_payload(claim: EvidenceClaim) -> dict[str, Any]:
    """Return every deterministic claim field except its self-addressing ID."""

    value = claim.to_dict()
    value.pop("evidence_id")
    return value


def _validate_bridge_claim(claim: EvidenceClaim) -> None:
    if not isinstance(claim, EvidenceClaim):
        raise ValidationError("claim must be EvidenceClaim")
    if claim.channel != RNA_CONSEQUENCE_CHANNEL:
        raise ValidationError("claim is not in the matched RNA consequence channel")
    if claim.produced_by != PRODUCED_BY or claim.created_at != DETERMINISTIC_CREATED_AT:
        raise ValidationError("claim was not produced by the deterministic RNA bridge")
    if claim.tier is not EvidenceTier.COMPUTED:
        raise ValidationError("matched RNA bridge claims must use the computed tier")
    _assert_sample_free(claim.payload)
    payload = _mapping(claim.payload, "claim payload")
    _strict_keys(
        payload,
        required=frozenset(
            {
                "schema_version",
                "target",
                "rna_consequence",
                "derivation",
                "policy",
                "source_addresses",
                "privacy",
            }
        ),
        optional=frozenset({"retained_owner_address"}),
        label="claim payload",
    )
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValidationError("unsupported RNA claim payload schema_version")

    target_raw = _mapping(payload.get("target"), "target")
    _strict_keys(
        target_raw,
        required=frozenset(
            {
                "variant_id",
                "element_id",
                "gene_id",
                "context_key",
                "target_address",
            }
        ),
        label="claim target",
    )
    target = RNAElementGeneTarget(
        variant_id=target_raw.get("variant_id"),
        element_id=target_raw.get("element_id"),
        gene_id=target_raw.get("gene_id"),
        context=claim.context,
    )
    if target_raw.get("context_key") != target.context.key:
        raise ValidationError("claim target context_key disagrees with claim context")
    if target_raw.get("target_address") != target.content_address:
        raise ValidationError("claim target_address does not match its target")

    consequence = RNAConsequenceEvidence.from_mapping(
        _mapping(payload.get("rna_consequence"), "rna_consequence")
    )
    policy_raw = _mapping(payload.get("policy"), "policy")
    _strict_keys(
        policy_raw,
        required=frozenset(DEFAULT_RNA_CLAIM_POLICY.to_dict()),
        label="claim policy",
    )
    if policy_raw.get("schema_version") != SCHEMA_VERSION:
        raise ValidationError("unsupported RNA claim policy schema_version")
    policy = RNAClaimPolicy(
        expression_saturation_z=policy_raw.get("expression_saturation_z"),
        allelic_saturation_log2_ratio=policy_raw.get("allelic_saturation_log2_ratio"),
        allelic_q_reference=policy_raw.get("allelic_q_reference"),
        max_directional_score=policy_raw.get("max_directional_score"),
        measured_negative_score=policy_raw.get("measured_negative_score"),
        single_component_confidence=policy_raw.get("single_component_confidence"),
        multi_component_confidence=policy_raw.get("multi_component_confidence"),
    )
    owner_address = (
        _retained_owner_address(payload["retained_owner_address"])
        if "retained_owner_address" in payload
        else None
    )
    expected = rna_consequence_to_claim(
        consequence,
        target,
        policy=policy,
        retained_owner_address=owner_address,
    )
    if claim.to_dict() != expected.to_dict():
        raise ValidationError(
            "claim content or evidence_id does not match its consequence, target, and policy"
        )

    digest = content_hash(_claim_identity_payload(claim)).split(":", 1)[1]
    if claim.evidence_id != f"ev-rna-{digest[:20]}":
        raise ValidationError("claim evidence_id does not match its edge and consequence")


_CLAIM_FIELDS = frozenset(
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


def _claim_from_mapping(raw: Mapping[str, Any]) -> EvidenceClaim:
    value = _mapping(raw, "evidence claim")
    _strict_keys(value, required=_CLAIM_FIELDS, label="evidence claim")
    depends_on = _sequence(value.get("depends_on"), "depends_on")
    try:
        state = EvidenceState(str(value.get("state")))
        tier = EvidenceTier(str(value.get("tier")))
    except ValueError as error:
        raise ValidationError("claim contains an unsupported state or tier") from error
    claim = EvidenceClaim(
        evidence_id=_text(value.get("evidence_id"), "evidence_id"),
        edge_id=_text(value.get("edge_id"), "edge_id"),
        source_id=_text(value.get("source_id"), "source_id"),
        channel=_text(value.get("channel"), "channel"),
        state=state,
        tier=tier,
        score=(None if value.get("score") is None else _finite(value.get("score"), "score")),
        confidence=_finite(value.get("confidence"), "confidence"),
        context=ReferenceContext.from_dict(_mapping(value.get("context"), "context")),
        summary=_text(value.get("summary"), "summary"),
        payload=dict(_mapping(value.get("payload"), "payload")),
        depends_on=tuple(_text(item, "dependency") for item in depends_on),
        produced_by=_text(value.get("produced_by"), "produced_by"),
        created_at=_text(value.get("created_at"), "created_at"),
        supersedes=(
            None
            if value.get("supersedes") is None
            else _text(value.get("supersedes"), "supersedes")
        ),
    )
    _validate_bridge_claim(claim)
    return claim


@dataclass(frozen=True, slots=True)
class RNAClaimBatch:
    """Deterministic result of fail-closed consequence-to-target matching."""

    evidence_addresses: tuple[str, ...]
    target_addresses: tuple[str, ...]
    claims: tuple[EvidenceClaim, ...]
    unmatched_evidence_addresses: tuple[str, ...] = ()
    ambiguous_evidence_addresses: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name in (
            "evidence_addresses",
            "target_addresses",
            "unmatched_evidence_addresses",
            "ambiguous_evidence_addresses",
        ):
            raw_values = _bounded_batch_rows(getattr(self, field_name), field_name)
            values = tuple(sorted(_text(item, field_name) for item in raw_values))
            if len(values) != len(set(values)):
                raise ValidationError(f"{field_name} must not contain duplicates")
            object.__setattr__(self, field_name, values)

        claim_rows = _bounded_batch_rows(self.claims, "claims")
        if any(not isinstance(item, EvidenceClaim) for item in claim_rows):
            raise ValidationError("claims must contain only EvidenceClaim objects")
        claims = tuple(sorted(claim_rows, key=lambda item: (item.edge_id, item.evidence_id)))
        for claim in claims:
            _validate_bridge_claim(claim)
        if len({claim.evidence_id for claim in claims}) != len(claims):
            raise ValidationError("RNA claim batch contains duplicate evidence IDs")
        object.__setattr__(self, "claims", claims)

        evidence_set = set(self.evidence_addresses)
        unmatched = set(self.unmatched_evidence_addresses)
        ambiguous = set(self.ambiguous_evidence_addresses)
        if not unmatched <= evidence_set or not ambiguous <= evidence_set:
            raise ValidationError("unmatched and ambiguous addresses must belong to the batch")
        if unmatched & ambiguous:
            raise ValidationError("an evidence item cannot be unmatched and ambiguous")
        matched = {_bridge_claim_consequence_address(claim) for claim in claims}
        if len(matched) != len(claims):
            raise ValidationError("one RNA consequence cannot emit multiple batch claims")
        if matched != evidence_set - unmatched - ambiguous:
            raise ValidationError("claim and matching-status addresses are not conserved")
        used_targets = {_bridge_claim_target_address(claim) for claim in claims}
        if not used_targets <= set(self.target_addresses):
            raise ValidationError("claim references a target outside the batch")

    @property
    def matched_evidence_addresses(self) -> tuple[str, ...]:
        return tuple(sorted(_bridge_claim_consequence_address(claim) for claim in self.claims))

    @property
    def unmatched_target_addresses(self) -> tuple[str, ...]:
        used = {_bridge_claim_target_address(claim) for claim in self.claims}
        return tuple(sorted(set(self.target_addresses) - used))

    @property
    def complete(self) -> bool:
        return (
            not self.unmatched_evidence_addresses
            and not self.ambiguous_evidence_addresses
            and not self.unmatched_target_addresses
        )

    def _payload(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "evidence_count": len(self.evidence_addresses),
            "target_count": len(self.target_addresses),
            "claim_count": len(self.claims),
            "matched_count": len(self.matched_evidence_addresses),
            "unmatched_count": len(self.unmatched_evidence_addresses),
            "ambiguous_count": len(self.ambiguous_evidence_addresses),
            "unmatched_target_count": len(self.unmatched_target_addresses),
            "complete": self.complete,
            "evidence_addresses": list(self.evidence_addresses),
            "target_addresses": list(self.target_addresses),
            "matched_evidence_addresses": list(self.matched_evidence_addresses),
            "unmatched_evidence_addresses": list(self.unmatched_evidence_addresses),
            "ambiguous_evidence_addresses": list(self.ambiguous_evidence_addresses),
            "unmatched_target_addresses": list(self.unmatched_target_addresses),
            "claims": [claim.to_dict() for claim in self.claims],
        }

    @property
    def content_address(self) -> str:
        return content_hash(self._payload(), prefix="rna-claim-batch")

    def to_dict(self) -> dict[str, Any]:
        value = self._payload() | {"content_address": self.content_address}
        _assert_sample_free(value)
        return value

    public_projection = to_dict
    to_public_dict = to_dict

    def to_json(self) -> str:
        return canonical_json(self.to_dict())

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> RNAClaimBatch:
        value = _mapping(raw, "RNA claim batch")
        derived_fields = frozenset(
            {
                "schema_version",
                "evidence_count",
                "target_count",
                "claim_count",
                "matched_count",
                "unmatched_count",
                "ambiguous_count",
                "unmatched_target_count",
                "complete",
                "evidence_addresses",
                "target_addresses",
                "matched_evidence_addresses",
                "unmatched_evidence_addresses",
                "ambiguous_evidence_addresses",
                "unmatched_target_addresses",
                "claims",
            }
        )
        _strict_keys(
            value,
            required=derived_fields,
            optional=frozenset({"content_address"}),
            label="RNA claim batch",
        )
        if value.get("schema_version") != SCHEMA_VERSION:
            raise ValidationError("unsupported RNA claim batch schema_version")
        result = cls(
            evidence_addresses=_bounded_batch_rows(
                (
                    _text(item, "evidence address")
                    for item in _sequence(value.get("evidence_addresses"), "evidence_addresses")
                ),
                "evidence_addresses",
            ),
            target_addresses=_bounded_batch_rows(
                (
                    _text(item, "target address")
                    for item in _sequence(value.get("target_addresses"), "target_addresses")
                ),
                "target_addresses",
            ),
            claims=_bounded_batch_rows(
                (
                    _claim_from_mapping(_mapping(item, "claim"))
                    for item in _sequence(value.get("claims"), "claims")
                ),
                "claims",
            ),
            unmatched_evidence_addresses=_bounded_batch_rows(
                (
                    _text(item, "unmatched evidence address")
                    for item in _sequence(
                        value.get("unmatched_evidence_addresses"),
                        "unmatched_evidence_addresses",
                    )
                ),
                "unmatched_evidence_addresses",
            ),
            ambiguous_evidence_addresses=_bounded_batch_rows(
                (
                    _text(item, "ambiguous evidence address")
                    for item in _sequence(
                        value.get("ambiguous_evidence_addresses"),
                        "ambiguous_evidence_addresses",
                    )
                ),
                "ambiguous_evidence_addresses",
            ),
        )
        expected = result._payload()
        for field_name in derived_fields:
            if value.get(field_name) != expected[field_name]:
                raise ValidationError(f"RNA claim batch {field_name} is not conserved")
        _verify_address(value, result.content_address, "RNA claim batch")
        return result

    @classmethod
    def from_json(cls, text: str) -> RNAClaimBatch:
        return cls.from_mapping(_json_mapping(text, "RNA claim batch"))


def match_rna_consequences(
    evidence: Iterable[RNAConsequenceEvidence],
    targets: Iterable[RNAElementGeneTarget],
    *,
    policy: RNAClaimPolicy = DEFAULT_RNA_CLAIM_POLICY,
    require_complete: bool = False,
    retained_owner_address: str | None = None,
) -> RNAClaimBatch:
    """Match by variant, gene/feature, and context; never guess ambiguity.

    A consequence that matches no target is reported as unmatched.  A
    consequence that matches more than one element target is reported as
    ambiguous and emits no claim.  Input order does not affect any output.
    Each iterable is consumed only through the advertised batch maximum plus
    one sentinel item, so unbounded producers fail closed.
    """

    if not isinstance(policy, RNAClaimPolicy):
        raise ValidationError("policy must be RNAClaimPolicy")
    if not isinstance(require_complete, bool):
        raise ValidationError("require_complete must be boolean")
    owner_address = _retained_owner_address(retained_owner_address)
    evidence_rows = _bounded_batch_rows(evidence, "evidence")
    for item in evidence_rows:
        validate_rna_consequence(item)
    evidence_addresses = tuple(item.content_address for item in evidence_rows)
    if len(evidence_addresses) != len(set(evidence_addresses)):
        raise ValidationError("evidence contains duplicate RNA consequences")

    target_rows = _bounded_batch_rows(targets, "targets")
    if any(not isinstance(item, RNAElementGeneTarget) for item in target_rows):
        raise ValidationError("targets must contain only RNAElementGeneTarget objects")
    target_addresses = tuple(item.content_address for item in target_rows)
    if len(target_addresses) != len(set(target_addresses)):
        raise ValidationError("targets contains duplicate destinations")

    targets_by_key: dict[tuple[str, str, str], list[RNAElementGeneTarget]] = {}
    for target in target_rows:
        targets_by_key.setdefault(target.match_key, []).append(target)

    claims: list[EvidenceClaim] = []
    unmatched: list[str] = []
    ambiguous: list[str] = []
    for item in sorted(evidence_rows, key=lambda row: row.content_address):
        key = (item.variant_id, item.feature_id, item.context_key)
        candidates = targets_by_key.get(key, [])
        if not candidates:
            unmatched.append(item.content_address)
        elif len(candidates) > 1:
            ambiguous.append(item.content_address)
        else:
            claims.append(
                rna_consequence_to_claim(
                    item,
                    candidates[0],
                    policy=policy,
                    retained_owner_address=owner_address,
                )
            )

    batch = RNAClaimBatch(
        evidence_addresses=evidence_addresses,
        target_addresses=target_addresses,
        claims=tuple(claims),
        unmatched_evidence_addresses=tuple(unmatched),
        ambiguous_evidence_addresses=tuple(ambiguous),
    )
    if require_complete and not batch.complete:
        raise ValidationError(
            "RNA claim matching is incomplete: "
            f"{len(batch.unmatched_evidence_addresses)} unmatched evidence, "
            f"{len(batch.ambiguous_evidence_addresses)} ambiguous evidence, "
            f"{len(batch.unmatched_target_addresses)} unmatched targets"
        )
    return batch


def expression_claims_capabilities() -> dict[str, Any]:
    """Return the stable operational and privacy contract for this bridge."""

    body: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "module": "glio_noncode.expression_claims",
        "operations": [
            "deterministic_element_gene_edge_addressing",
            "exact_three_key_matching",
            "fail_closed_ambiguity_detection",
            "bounded_batch_matching",
            "native_evidence_claim_projection",
            "deterministic_batch_round_trip",
            "retained_owner_dependency_binding",
        ],
        "match_dimensions": ["variant_id", "feature_id/gene_id", "ReferenceContext.key"],
        "channel": RNA_CONSEQUENCE_CHANNEL,
        "channel_grouping": "one correlated matched-RNA channel per element-gene edge",
        "native_state_mapping": {
            source.value: target.value for source, target in _STATE_MAP.items()
        },
        "score_semantics": {
            "kind": "bounded evidence strength, not probability",
            "directional_components_are_summed": False,
            "out_of_domain_score": None,
            "abstained_score": None,
            "default_policy": DEFAULT_RNA_CLAIM_POLICY.to_dict(),
        },
        "privacy": {
            "sample_free_payloads": True,
            "raw_measurements_excluded": True,
            "cohort_vectors_excluded": True,
        },
        "ambiguity_policy": "emit no claim until exactly one element target matches",
        "dependency_modes": {
            "standalone": "depends_on contains the typed leaf source addresses",
            "retained_owner": (
                "depends_on contains exactly the canonical sha256 retained_owner_address; "
                "typed leaf addresses remain in payload.source_addresses"
            ),
        },
        "limits": {
            "max_evidence_items": MAX_RNA_CLAIM_BATCH_ITEMS,
            "max_target_items": MAX_RNA_CLAIM_BATCH_ITEMS,
        },
    }
    return body | {"content_address": content_hash(body, prefix="expression-claims-capabilities")}


def expression_claims_schema() -> dict[str, Any]:
    """Return a compact JSON Schema for targets, claims, and batch surfaces."""

    state_values = [item.value for item in EvidenceState]
    body: dict[str, Any] = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "urn:glio-noncode:expression-claims:1",
        "title": "Matched RNA native evidence claims",
        "schema_version": SCHEMA_VERSION,
        "$defs": {
            "RNAElementGeneTarget": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "schema_version",
                    "variant_id",
                    "element_id",
                    "gene_id",
                    "context",
                    "context_key",
                    "edge_id",
                    "content_address",
                ],
                "properties": {
                    "schema_version": {"const": SCHEMA_VERSION},
                    "variant_id": {"type": "string", "minLength": 1},
                    "element_id": {"type": "string", "minLength": 1},
                    "gene_id": {"type": "string", "minLength": 1},
                    "context": {"type": "object"},
                    "context_key": {"type": "string", "minLength": 1},
                    "edge_id": {"type": "string", "pattern": "^edge-[0-9a-f]{20}$"},
                    "content_address": {
                        "type": "string",
                        "pattern": "^rna-claim-target:[0-9a-f]{64}$",
                    },
                },
            },
            "EvidenceClaim": {
                "type": "object",
                "additionalProperties": False,
                "required": sorted(_CLAIM_FIELDS),
                "properties": {
                    "evidence_id": {
                        "type": "string",
                        "pattern": "^ev-rna-[0-9a-f]{20}$",
                    },
                    "edge_id": {"type": "string", "pattern": "^edge-[0-9a-f]{20}$"},
                    "source_id": {"type": "string", "minLength": 1},
                    "channel": {"const": RNA_CONSEQUENCE_CHANNEL},
                    "state": {"enum": state_values},
                    "tier": {"const": EvidenceTier.COMPUTED.value},
                    "score": {"type": ["number", "null"], "minimum": 0, "maximum": 1},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "context": {"type": "object"},
                    "summary": {"type": "string", "minLength": 1},
                    "payload": {
                        "type": "object",
                        "properties": {
                            "retained_owner_address": {
                                "type": "string",
                                "pattern": "^sha256:[0-9a-f]{64}$",
                                "description": (
                                    "When present, depends_on contains exactly this retained "
                                    "RNA batch address."
                                ),
                            }
                        },
                    },
                    "depends_on": {"type": "array", "items": {"type": "string"}},
                    "produced_by": {"const": PRODUCED_BY},
                    "created_at": {"const": DETERMINISTIC_CREATED_AT},
                    "supersedes": {"type": ["string", "null"]},
                },
            },
            "RNAClaimBatch": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "schema_version",
                    "evidence_count",
                    "target_count",
                    "claim_count",
                    "matched_count",
                    "unmatched_count",
                    "ambiguous_count",
                    "unmatched_target_count",
                    "complete",
                    "evidence_addresses",
                    "target_addresses",
                    "matched_evidence_addresses",
                    "unmatched_evidence_addresses",
                    "ambiguous_evidence_addresses",
                    "unmatched_target_addresses",
                    "claims",
                    "content_address",
                ],
                "properties": {
                    "schema_version": {"const": SCHEMA_VERSION},
                    "evidence_count": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": MAX_RNA_CLAIM_BATCH_ITEMS,
                    },
                    "target_count": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": MAX_RNA_CLAIM_BATCH_ITEMS,
                    },
                    "claim_count": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": MAX_RNA_CLAIM_BATCH_ITEMS,
                    },
                    "matched_count": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": MAX_RNA_CLAIM_BATCH_ITEMS,
                    },
                    "unmatched_count": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": MAX_RNA_CLAIM_BATCH_ITEMS,
                    },
                    "ambiguous_count": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": MAX_RNA_CLAIM_BATCH_ITEMS,
                    },
                    "unmatched_target_count": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": MAX_RNA_CLAIM_BATCH_ITEMS,
                    },
                    "complete": {"type": "boolean"},
                    "evidence_addresses": {
                        "type": "array",
                        "maxItems": MAX_RNA_CLAIM_BATCH_ITEMS,
                        "uniqueItems": True,
                        "items": {"type": "string"},
                    },
                    "target_addresses": {
                        "type": "array",
                        "maxItems": MAX_RNA_CLAIM_BATCH_ITEMS,
                        "uniqueItems": True,
                        "items": {"type": "string"},
                    },
                    "matched_evidence_addresses": {
                        "type": "array",
                        "maxItems": MAX_RNA_CLAIM_BATCH_ITEMS,
                        "uniqueItems": True,
                        "items": {"type": "string"},
                    },
                    "unmatched_evidence_addresses": {
                        "type": "array",
                        "maxItems": MAX_RNA_CLAIM_BATCH_ITEMS,
                        "uniqueItems": True,
                        "items": {"type": "string"},
                    },
                    "ambiguous_evidence_addresses": {
                        "type": "array",
                        "maxItems": MAX_RNA_CLAIM_BATCH_ITEMS,
                        "uniqueItems": True,
                        "items": {"type": "string"},
                    },
                    "unmatched_target_addresses": {
                        "type": "array",
                        "maxItems": MAX_RNA_CLAIM_BATCH_ITEMS,
                        "uniqueItems": True,
                        "items": {"type": "string"},
                    },
                    "claims": {
                        "type": "array",
                        "maxItems": MAX_RNA_CLAIM_BATCH_ITEMS,
                        "items": {"$ref": "#/$defs/EvidenceClaim"},
                    },
                    "content_address": {
                        "type": "string",
                        "pattern": "^rna-claim-batch:[0-9a-f]{64}$",
                    },
                },
            },
        },
    }
    return body | {"content_address": content_hash(body, prefix="expression-claims-schema")}


def public_projection(value: object) -> dict[str, Any]:
    """Return only bridge-owned, sample-free public structures."""

    if isinstance(value, EvidenceClaim):
        _validate_bridge_claim(value)
        projection = value.to_dict()
    elif isinstance(value, (RNAElementGeneTarget, RNAClaimBatch)):
        projection = value.to_dict()
    else:
        raise ValidationError("value is not an expression-claims public object")
    _assert_sample_free(projection)
    return projection


build_rna_claim = rna_consequence_to_claim
build_rna_claims = match_rna_consequences
capabilities = expression_claims_capabilities
capability_manifest = expression_claims_capabilities
schema = expression_claims_schema
schema_contract = expression_claims_schema


__all__ = [
    "DEFAULT_RNA_CLAIM_POLICY",
    "DETERMINISTIC_CREATED_AT",
    "MAX_RNA_CLAIM_BATCH_ITEMS",
    "PRODUCED_BY",
    "RNA_CONSEQUENCE_CHANNEL",
    "RNAClaimBatch",
    "RNAClaimDerivation",
    "RNAClaimPolicy",
    "RNAElementGeneTarget",
    "build_rna_claim",
    "build_rna_claims",
    "capabilities",
    "capability_manifest",
    "element_gene_edge_id",
    "expression_claims_capabilities",
    "expression_claims_schema",
    "match_rna_consequences",
    "matches_rna_consequence",
    "public_projection",
    "rna_consequence_to_claim",
    "schema",
    "schema_contract",
    "validate_rna_consequence",
]
