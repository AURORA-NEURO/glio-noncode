"""Input, graph, and release validation with explainable issue codes."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, fields
from enum import Enum
from typing import Any, cast

from .data_sources import FetchReceipt, FetchStatus
from .errors import ValidationError
from .evidence import EvidenceGraph, EvidenceGraphLimits
from .models import (
    AssayType,
    CandidateElement,
    CaseManifest,
    Dossier,
    EdgeType,
    EvidenceClaim,
    EvidenceState,
    EvidenceTier,
    ExperimentOption,
    Hypothesis,
    HypothesisEdge,
    ReferenceContext,
    ResearchStatus,
    ReviewDecision,
    ReviewState,
    SupportLevel,
    VariantIdentity,
    VariantKind,
    VariantOrigin,
)
from .policy import PolicyDecision, ResearchPolicy
from .serialization import (
    _FrozenJsonArray,
    _FrozenJsonObject,
    canonical_bytes,
    content_hash,
)

MAX_VALIDATION_VARIANTS = 1_000
MAX_VALIDATION_ELEMENTS = 100_000
MAX_VALIDATION_HYPOTHESES = 10_000
MAX_VALIDATION_EVIDENCE_CLAIMS = 20_000
MAX_VALIDATION_EXPERIMENTS = 10_000
MAX_VALIDATION_EDGES_PER_HYPOTHESIS = 1_024
MAX_VALIDATION_TOTAL_EDGES = 20_000
MAX_VALIDATION_CLAIMS_PER_EDGE = 10_000
MAX_VALIDATION_DEPENDENCIES_PER_CLAIM = 10_000
MAX_VALIDATION_SOURCE_RECEIPTS = 256_000
MAX_VALIDATION_SOURCE_BUNDLES = 2_000
MAX_VALIDATION_SEQUENCE_ITEMS = 256_000
MAX_VALIDATION_STRUCTURED_NODES = 1_000_000
MAX_VALIDATION_STRUCTURED_DEPTH = 64
MAX_VALIDATION_STRING_CHARACTERS = 16_777_216
MAX_VALIDATION_TOTAL_CHARACTERS = 134_217_728
MAX_VALIDATION_CANONICAL_BYTES = 134_217_728
MAX_VALIDATION_ISSUES = 100_000


def _bounded_positive_integer(value: object, field_name: str, ceiling: int) -> int:
    if type(value) is not int:
        raise ValidationError(f"{field_name} must be an integer")
    if value <= 0:
        raise ValidationError(f"{field_name} must be positive")
    if value > ceiling:
        raise ValidationError(f"{field_name} exceeds the safety ceiling of {ceiling}")
    return value


@dataclass(frozen=True, slots=True)
class ValidationLimits:
    """Downward-configurable work and output limits for contract validation."""

    max_variants: int = MAX_VALIDATION_VARIANTS
    max_elements: int = MAX_VALIDATION_ELEMENTS
    max_hypotheses: int = MAX_VALIDATION_HYPOTHESES
    max_evidence_claims: int = MAX_VALIDATION_EVIDENCE_CLAIMS
    max_experiments: int = MAX_VALIDATION_EXPERIMENTS
    max_edges_per_hypothesis: int = MAX_VALIDATION_EDGES_PER_HYPOTHESIS
    max_total_edges: int = MAX_VALIDATION_TOTAL_EDGES
    max_claims_per_edge: int = MAX_VALIDATION_CLAIMS_PER_EDGE
    max_dependencies_per_claim: int = MAX_VALIDATION_DEPENDENCIES_PER_CLAIM
    max_source_receipts: int = MAX_VALIDATION_SOURCE_RECEIPTS
    max_source_bundles: int = MAX_VALIDATION_SOURCE_BUNDLES
    max_sequence_items: int = MAX_VALIDATION_SEQUENCE_ITEMS
    max_structured_nodes: int = MAX_VALIDATION_STRUCTURED_NODES
    max_structured_depth: int = MAX_VALIDATION_STRUCTURED_DEPTH
    max_string_characters: int = MAX_VALIDATION_STRING_CHARACTERS
    max_total_characters: int = MAX_VALIDATION_TOTAL_CHARACTERS
    max_canonical_bytes: int = MAX_VALIDATION_CANONICAL_BYTES
    max_issues: int = MAX_VALIDATION_ISSUES

    def __post_init__(self) -> None:
        for field_name, ceiling in (
            ("max_variants", 1_000),
            ("max_elements", 100_000),
            ("max_hypotheses", 10_000),
            ("max_evidence_claims", 20_000),
            ("max_experiments", 10_000),
            ("max_edges_per_hypothesis", 1_024),
            ("max_total_edges", 20_000),
            ("max_claims_per_edge", 10_000),
            ("max_dependencies_per_claim", 10_000),
            ("max_source_receipts", 256_000),
            ("max_source_bundles", 2_000),
            ("max_sequence_items", 256_000),
            ("max_structured_nodes", 1_000_000),
            ("max_structured_depth", 64),
            ("max_string_characters", 16_777_216),
            ("max_total_characters", 134_217_728),
            ("max_canonical_bytes", 134_217_728),
            ("max_issues", 100_000),
        ):
            object.__setattr__(
                self,
                field_name,
                _bounded_positive_integer(getattr(self, field_name), field_name, ceiling),
            )


DEFAULT_VALIDATION_LIMITS = ValidationLimits()

_RECEIPT_FIELDS = frozenset(
    {
        "source_id",
        "source_version",
        "url",
        "request_hash",
        "response_hash",
        "status",
        "http_status",
        "attempts",
        "retrieved_at",
        "elapsed_seconds",
        "cache_expires_at",
        "warnings",
        "error_type",
        "error_message",
    }
)
_MODEL_TYPES = frozenset(
    {
        ReferenceContext,
        VariantIdentity,
        CandidateElement,
        CaseManifest,
        EvidenceClaim,
        HypothesisEdge,
        Hypothesis,
        ExperimentOption,
        ReviewDecision,
        Dossier,
    }
)
_MODEL_ENUM_TYPES = frozenset(
    {
        VariantKind,
        VariantOrigin,
        EvidenceState,
        EvidenceTier,
        EdgeType,
        SupportLevel,
        ResearchStatus,
        ReviewState,
        AssayType,
    }
)


def _is_content_address(value: object) -> bool:
    if type(value) is not str or len(value) > 193:
        return False
    prefix, separator, digest = value.rpartition(":")
    return (
        separator == ":"
        and 1 <= len(prefix) <= 128
        and prefix[0].isascii()
        and prefix[0].islower()
        and all(
            character.isascii()
            and (character.islower() or character.isdigit() or character in "._-")
            for character in prefix
        )
        and len(digest) == 64
        and all(character in "0123456789abcdef" for character in digest)
    )


def _is_sha256_address(value: object) -> bool:
    return type(value) is str and value.startswith("sha256:") and _is_content_address(value)


def _safe_exception(error: Exception) -> str:
    try:
        text = str(error).replace("\r", " ").replace("\n", " ").strip()
    except Exception:  # noqa: BLE001 - hostile exception rendering must fail closed
        text = type(error).__name__
    return (text or type(error).__name__)[:512]


class IssueSeverity(str, Enum):  # noqa: UP042 - preserve historical str(member) behavior
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    code: str
    severity: IssueSeverity
    message: str
    path: str
    remediation: str

    def __post_init__(self) -> None:
        if (
            type(self.code) is not str
            or not self.code
            or len(self.code) > 128
            or not self.code.replace("_", "").isalnum()
            or self.code.lower() != self.code
        ):
            raise ValidationError("validation issue code must be a bounded lowercase identifier")
        if type(self.severity) is not IssueSeverity:
            raise ValidationError("validation issue severity must be an IssueSeverity")
        for field_name in ("message", "path", "remediation"):
            value = getattr(self, field_name)
            if type(value) is not str or not value.strip():
                raise ValidationError(f"validation issue {field_name} must be a non-empty string")
            if len(value) > 16_384:
                raise ValidationError(
                    f"validation issue {field_name} exceeds the safety ceiling of 16384 characters"
                )

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "severity": self.severity.value,
            "message": self.message,
            "path": self.path,
            "remediation": self.remediation,
        }


@dataclass(frozen=True, slots=True)
class ValidationReport:
    valid: bool
    issues: tuple[ValidationIssue, ...]

    def __post_init__(self) -> None:
        if type(self.valid) is not bool:
            raise ValidationError("validation report valid must be a boolean")
        if type(self.issues) is not tuple or any(
            type(issue) is not ValidationIssue for issue in self.issues
        ):
            raise ValidationError("validation report issues must be a tuple of ValidationIssue")
        if len(self.issues) > 100_000:
            raise ValidationError("validation report exceeds the safety ceiling of 100000 issues")
        expected_valid = not any(issue.severity is IssueSeverity.ERROR for issue in self.issues)
        if self.valid is not expected_valid:
            raise ValidationError(
                "validation report valid flag does not match its issue severities"
            )

    def to_dict(self) -> dict[str, object]:
        return {"valid": self.valid, "issues": [issue.to_dict() for issue in self.issues]}


class _PreflightFailure(Exception):
    def __init__(self, code: str, message: str, path: str) -> None:
        super().__init__(message)
        self.code = code
        self.path = path


class _BudgetFailure(Exception):
    def __init__(self, message: str, path: str) -> None:
        super().__init__(message)
        self.path = path


def _error(code: str, message: str, path: str, remediation: str) -> ValidationIssue:
    return ValidationIssue(code, IssueSeverity.ERROR, message, path, remediation)


def _report(issues: list[ValidationIssue] | tuple[ValidationIssue, ...]) -> ValidationReport:
    unique = {
        (issue.code, issue.severity.value, issue.message, issue.path, issue.remediation): issue
        for issue in issues
    }
    ordered = tuple(
        sorted(
            unique.values(),
            key=lambda issue: (
                issue.path,
                issue.code,
                issue.severity.value,
                issue.message,
                issue.remediation,
            ),
        )
    )
    return ValidationReport(
        valid=not any(issue.severity is IssueSeverity.ERROR for issue in ordered),
        issues=ordered,
    )


def _single_error(code: str, message: str, path: str, remediation: str) -> ValidationReport:
    return _report((_error(code, message, path, remediation),))


class _BoundedIssueList(list[ValidationIssue]):
    """Collect issues without allowing adversarial input to expand report memory."""

    def __init__(self, limit: int) -> None:
        super().__init__()
        self.limit = limit
        self.truncated = False

    def append(self, issue: ValidationIssue, /) -> None:
        if self.truncated:
            return
        if len(self) < self.limit:
            super().append(issue)
            return
        self.truncated = True
        marker = _error(
            "validation_issue_limit_exceeded",
            "Validation found more issues than the configured reporting limit.",
            "validation",
            "Reduce the input or raise the reporting limit within its hard safety ceiling.",
        )
        if self.limit == 1:
            self[0] = marker
        else:
            self[-1] = marker

    def extend(self, issues: Any, /) -> None:
        for issue in issues:
            self.append(issue)


def _validated_limits(value: object) -> ValidationLimits:
    if type(value) is not ValidationLimits:
        raise ValidationError("limits must be ValidationLimits")
    return ValidationLimits(
        **{field.name: getattr(value, field.name) for field in fields(ValidationLimits)}
    )


def _require_tuple(value: object, path: str, maximum: int) -> tuple[Any, ...]:
    if type(value) is not tuple:
        raise _PreflightFailure(
            "noncanonical_object_graph",
            f"{path} must be a tuple in a canonical typed object.",
            path,
        )
    if len(value) > maximum:
        raise _BudgetFailure(
            f"{path} exceeds the configured maximum of {maximum} items.",
            path,
        )
    return value


def _require_exact_type(value: object, expected: type[Any], path: str) -> None:
    if type(value) is not expected:
        raise _PreflightFailure(
            "noncanonical_object_graph",
            f"{path} must be an exact {expected.__name__} object.",
            path,
        )


def _measure_model(value: object, limits: ValidationLimits) -> None:
    nodes = 0
    characters = 0
    active: set[int] = set()

    def walk(item: object, path: str, depth: int) -> None:
        nonlocal nodes, characters
        if depth > limits.max_structured_depth:
            raise _BudgetFailure(
                f"{path} exceeds the configured structured depth of {limits.max_structured_depth}.",
                path,
            )
        nodes += 1
        if nodes > limits.max_structured_nodes:
            raise _BudgetFailure(
                "The object graph exceeds the configured maximum of "
                f"{limits.max_structured_nodes} nodes.",
                path,
            )
        if item is None or type(item) in {bool, int}:
            return
        if type(item) is float:
            if not math.isfinite(item):
                raise _PreflightFailure(
                    "noncanonical_object_graph",
                    f"{path} must contain only finite numbers.",
                    path,
                )
            return
        if type(item) is str:
            if len(item) > limits.max_string_characters:
                raise _BudgetFailure(
                    f"{path} exceeds the configured maximum of "
                    f"{limits.max_string_characters} characters.",
                    path,
                )
            characters += len(item)
            if characters > limits.max_total_characters:
                raise _BudgetFailure(
                    "The object graph exceeds the configured maximum of "
                    f"{limits.max_total_characters} string characters.",
                    path,
                )
            return
        if type(item) in _MODEL_ENUM_TYPES:
            walk(cast(Enum, item).value, path, depth + 1)
            return
        if type(item) in _MODEL_TYPES:
            marker = id(item)
            if marker in active:
                raise _PreflightFailure(
                    "noncanonical_object_graph",
                    f"{path} contains a recursive typed object.",
                    path,
                )
            active.add(marker)
            try:
                for model_field in fields(cast(Any, item)):
                    walk(
                        getattr(item, model_field.name),
                        f"{path}.{model_field.name}",
                        depth + 1,
                    )
            finally:
                active.remove(marker)
            return
        if type(item) in {tuple, _FrozenJsonArray}:
            sequence = cast(tuple[Any, ...] | _FrozenJsonArray, item)
            if len(sequence) > limits.max_sequence_items:
                raise _BudgetFailure(
                    f"{path} exceeds the configured maximum of {limits.max_sequence_items} items.",
                    path,
                )
            marker = id(item)
            if marker in active:
                raise _PreflightFailure(
                    "noncanonical_object_graph",
                    f"{path} contains a recursive sequence.",
                    path,
                )
            active.add(marker)
            try:
                for index, nested in enumerate(sequence):
                    walk(nested, f"{path}[{index}]", depth + 1)
            finally:
                active.remove(marker)
            return
        if type(item) is _FrozenJsonObject:
            mapping = cast(_FrozenJsonObject, item)
            if len(mapping) > limits.max_sequence_items:
                raise _BudgetFailure(
                    f"{path} exceeds the configured maximum of {limits.max_sequence_items} fields.",
                    path,
                )
            marker = id(item)
            if marker in active:
                raise _PreflightFailure(
                    "noncanonical_object_graph",
                    f"{path} contains a recursive object.",
                    path,
                )
            active.add(marker)
            try:
                for key, nested in mapping.items():
                    if type(key) is not str:
                        raise _PreflightFailure(
                            "noncanonical_object_graph",
                            f"{path} contains a non-string object key.",
                            path,
                        )
                    walk(key, f"{path}.<key>", depth + 1)
                    walk(nested, f"{path}.{key}", depth + 1)
            finally:
                active.remove(marker)
            return
        if isinstance(item, Enum):
            raise _PreflightFailure(
                "noncanonical_object_graph",
                f"{path} contains an unsupported enum type.",
                path,
            )
        raise _PreflightFailure(
            "noncanonical_object_graph",
            f"{path} contains non-canonical type {type(item).__name__}.",
            path,
        )

    walk(value, type(value).__name__, 0)


def _manifest_preflight(manifest: CaseManifest, limits: ValidationLimits) -> None:
    _require_exact_type(manifest.context, ReferenceContext, "context")
    variants = _require_tuple(manifest.variants, "variants", limits.max_variants)
    elements = _require_tuple(
        manifest.candidate_elements,
        "candidate_elements",
        limits.max_elements,
    )
    for index, variant in enumerate(variants):
        _require_exact_type(variant, VariantIdentity, f"variants[{index}]")
        _require_exact_type(variant.kind, VariantKind, f"variants[{index}].kind")
        _require_exact_type(variant.origin, VariantOrigin, f"variants[{index}].origin")
    for index, element in enumerate(elements):
        _require_exact_type(element, CandidateElement, f"candidate_elements[{index}]")
        _require_exact_type(
            element.context,
            ReferenceContext,
            f"candidate_elements[{index}].context",
        )


def _dossier_preflight(dossier: Dossier, limits: ValidationLimits) -> None:
    hypotheses = _require_tuple(dossier.hypotheses, "hypotheses", limits.max_hypotheses)
    evidence = _require_tuple(
        dossier.evidence,
        "evidence",
        limits.max_evidence_claims,
    )
    experiments = _require_tuple(
        dossier.experiments,
        "experiments",
        limits.max_experiments,
    )
    receipts = _require_tuple(
        dossier.source_receipts,
        "source_receipts",
        limits.max_source_receipts,
    )
    _require_tuple(
        dossier.source_bundle_addresses,
        "source_bundle_addresses",
        limits.max_source_bundles,
    )
    _require_tuple(dossier.warnings, "warnings", limits.max_sequence_items)
    _require_exact_type(dossier.status, ResearchStatus, "status")
    if type(dossier.research_use_only) is not bool:
        raise _PreflightFailure(
            "noncanonical_object_graph",
            "research_use_only must be an exact boolean.",
            "research_use_only",
        )
    if dossier.review is not None:
        _require_exact_type(dossier.review, ReviewDecision, "review")
        _require_exact_type(dossier.review.state, ReviewState, "review.state")

    edge_total = 0
    for index, hypothesis in enumerate(hypotheses):
        path = f"hypotheses[{index}]"
        _require_exact_type(hypothesis, Hypothesis, path)
        _require_exact_type(hypothesis.context, ReferenceContext, f"{path}.context")
        _require_exact_type(hypothesis.status, ResearchStatus, f"{path}.status")
        edges = _require_tuple(
            hypothesis.edges,
            f"{path}.edges",
            limits.max_edges_per_hypothesis,
        )
        edge_total += len(edges)
        if edge_total > limits.max_total_edges:
            raise _BudgetFailure(
                f"Dossier edges exceed the configured maximum of {limits.max_total_edges} items.",
                f"{path}.edges",
            )
        for edge_index, edge in enumerate(edges):
            edge_path = f"{path}.edges[{edge_index}]"
            _require_exact_type(edge, HypothesisEdge, edge_path)
            _require_exact_type(edge.edge_type, EdgeType, f"{edge_path}.edge_type")
            _require_exact_type(
                edge.support_level,
                SupportLevel,
                f"{edge_path}.support_level",
            )
            _require_tuple(
                edge.claim_ids,
                f"{edge_path}.claim_ids",
                limits.max_claims_per_edge,
            )
            _require_tuple(
                edge.alternatives,
                f"{edge_path}.alternatives",
                limits.max_sequence_items,
            )
        for field_name in (
            "missing_evidence",
            "negative_evidence",
            "alternatives",
            "provenance",
        ):
            _require_tuple(
                getattr(hypothesis, field_name),
                f"{path}.{field_name}",
                limits.max_sequence_items,
            )

    claims_per_edge: dict[str, int] = {}
    for index, claim in enumerate(evidence):
        path = f"evidence[{index}]"
        _require_exact_type(claim, EvidenceClaim, path)
        _require_exact_type(claim.context, ReferenceContext, f"{path}.context")
        _require_exact_type(claim.state, EvidenceState, f"{path}.state")
        _require_exact_type(claim.tier, EvidenceTier, f"{path}.tier")
        _require_tuple(
            claim.depends_on,
            f"{path}.depends_on",
            limits.max_dependencies_per_claim,
        )
        claims_per_edge[claim.edge_id] = claims_per_edge.get(claim.edge_id, 0) + 1
        if claims_per_edge[claim.edge_id] > limits.max_claims_per_edge:
            raise _BudgetFailure(
                f"Evidence edge {claim.edge_id!r} exceeds the configured maximum of "
                f"{limits.max_claims_per_edge} claims.",
                path,
            )

    for index, experiment in enumerate(experiments):
        path = f"experiments[{index}]"
        _require_exact_type(experiment, ExperimentOption, path)
        _require_exact_type(experiment.assay, AssayType, f"{path}.assay")
        for field_name in (
            "tests_edges",
            "required_context",
            "controls",
            "readouts",
            "limitations",
        ):
            _require_tuple(
                getattr(experiment, field_name),
                f"{path}.{field_name}",
                limits.max_sequence_items,
            )
    for index, receipt in enumerate(receipts):
        if type(receipt) is not _FrozenJsonObject:
            raise _PreflightFailure(
                "noncanonical_object_graph",
                f"source_receipts[{index}] must be a canonical immutable JSON object.",
                f"source_receipts[{index}]",
            )


def _canonical_payload(value: CaseManifest | Dossier, limits: ValidationLimits) -> dict[str, Any]:
    _measure_model(value, limits)
    raw = value.to_dict()
    encoded = canonical_bytes(raw)
    if len(encoded) > limits.max_canonical_bytes:
        raise _BudgetFailure(
            "Canonical payload exceeds the configured maximum of "
            f"{limits.max_canonical_bytes} bytes.",
            "content",
        )
    return raw


def _describe(values: set[str] | tuple[str, ...] | list[str], *, maximum: int = 8) -> str:
    ordered = sorted(set(values))
    displayed = ordered[:maximum]
    suffix = "" if len(ordered) <= maximum else f" (+{len(ordered) - maximum} more)"
    return f"{displayed}{suffix}"


def _parse_receipt(raw: Mapping[str, Any]) -> FetchReceipt:
    if set(raw) != _RECEIPT_FIELDS:
        unknown = sorted(set(raw) - _RECEIPT_FIELDS)
        missing = sorted(_RECEIPT_FIELDS - set(raw))
        raise ValidationError(
            f"receipt fields are not exact (missing={missing[:8]}, unknown={unknown[:8]})"
        )
    status_raw = raw["status"]
    if type(status_raw) is not str:
        raise ValidationError("receipt status must be a string")
    warnings_raw = raw["warnings"]
    if type(warnings_raw) is not _FrozenJsonArray or any(
        type(item) is not str for item in warnings_raw
    ):
        raise ValidationError("receipt warnings must be a canonical string array")
    receipt = FetchReceipt(
        source_id=raw["source_id"],
        source_version=raw["source_version"],
        url=raw["url"],
        request_hash=raw["request_hash"],
        response_hash=raw["response_hash"],
        status=FetchStatus(status_raw),
        http_status=raw["http_status"],
        attempts=raw["attempts"],
        retrieved_at=raw["retrieved_at"],
        elapsed_seconds=raw["elapsed_seconds"],
        cache_expires_at=raw["cache_expires_at"],
        warnings=tuple(warnings_raw),
        error_type=raw["error_type"],
        error_message=raw["error_message"],
    )
    if canonical_bytes(raw) != canonical_bytes(receipt.to_dict()):
        raise ValidationError("receipt is not an exact canonical FetchReceipt representation")
    return receipt


def _support_level(score: float) -> SupportLevel:
    if score >= 0.72:
        return SupportLevel.HIGH
    if score >= 0.45:
        return SupportLevel.MODERATE
    if score > 0:
        return SupportLevel.LOW
    return SupportLevel.UNKNOWN


class ContractValidator:
    """Validate immutable case contracts under explicit resource ceilings."""

    def __init__(self, *, limits: ValidationLimits | None = None) -> None:
        selected = DEFAULT_VALIDATION_LIMITS if limits is None else limits
        self.limits = _validated_limits(selected)

    def _limits_or_report(self) -> tuple[ValidationLimits | None, ValidationReport | None]:
        try:
            return _validated_limits(self.limits), None
        except (AttributeError, TypeError, ValidationError) as error:
            return None, _single_error(
                "invalid_validation_limits",
                f"Validation limits are invalid: {_safe_exception(error)}.",
                "validation.limits",
                "Restore an exact ValidationLimits instance within the hard safety ceilings.",
            )

    def validate_manifest(self, manifest: CaseManifest) -> ValidationReport:
        limits, invalid_limits = self._limits_or_report()
        if invalid_limits is not None:
            return invalid_limits
        if limits is None:  # pragma: no cover - paired return invariant above
            raise AssertionError("validated limits missing")
        if type(manifest) is not CaseManifest:
            return _single_error(
                "invalid_manifest_type",
                "Manifest must be an exact CaseManifest object.",
                "manifest",
                "Construct the manifest through CaseManifest.from_dict before validation.",
            )
        try:
            return self._validate_manifest_impl(manifest, limits)
        except _BudgetFailure as error:
            return _single_error(
                "validation_limit_exceeded",
                str(error),
                error.path,
                "Reduce the manifest or lower upstream producer bounds.",
            )
        except _PreflightFailure as error:
            return _single_error(
                error.code,
                str(error),
                error.path,
                "Rehydrate the manifest from its exact canonical typed representation.",
            )
        except Exception as error:  # noqa: BLE001 - public validation must fail closed
            return _single_error(
                "manifest_validation_failed",
                f"Manifest could not be validated safely: {_safe_exception(error)}.",
                "manifest",
                "Rehydrate the manifest from canonical JSON and retry validation.",
            )

    def _validate_manifest_impl(
        self,
        manifest: CaseManifest,
        limits: ValidationLimits,
    ) -> ValidationReport:
        _manifest_preflight(manifest, limits)
        raw = _canonical_payload(manifest, limits)
        issues = _BoundedIssueList(limits.max_issues)
        try:
            rehydrated = CaseManifest.from_dict(raw)
            if canonical_bytes(raw) != canonical_bytes(rehydrated.to_dict()):
                raise ValidationError("manifest does not round-trip exactly")
        except (OverflowError, RecursionError, TypeError, UnicodeError, ValueError) as error:
            issues.append(
                _error(
                    "noncanonical_manifest",
                    f"Manifest is not canonical: {_safe_exception(error)}.",
                    "manifest",
                    "Rebuild the manifest through CaseManifest.from_dict.",
                )
            )
        variant_builds = {variant.genome_build for variant in manifest.variants}
        if variant_builds != {manifest.context.genome_build}:
            issues.append(
                ValidationIssue(
                    "mixed_reference_build",
                    IssueSeverity.ERROR,
                    "Variant and case reference builds differ.",
                    "variants[*].genome_build",
                    "Normalize all variants to the declared case build or create an explicit "
                    "lift-over stage.",
                )
            )
        if not manifest.input_versions:
            issues.append(
                ValidationIssue(
                    "missing_input_versions",
                    IssueSeverity.WARNING,
                    "No input reference versions were declared.",
                    "input_versions",
                    "Record source and reference versions before comparing runs.",
                )
            )
        if manifest.subject_id.lower() in {"patient", "subject", "unknown"}:
            issues.append(
                ValidationIssue(
                    "weak_subject_identity",
                    IssueSeverity.WARNING,
                    "Subject identity is a placeholder.",
                    "subject_id",
                    "Use a local pseudonymous identifier that is stable within the project.",
                )
            )
        for index, element in enumerate(manifest.candidate_elements):
            if element.context.genome_build != manifest.context.genome_build:
                issues.append(
                    ValidationIssue(
                        "element_build_mismatch",
                        IssueSeverity.ERROR,
                        "Candidate element build differs from the case.",
                        f"candidate_elements[{index}].context.genome_build",
                        "Select an element source matching the case build.",
                    )
                )
            elif element.context.key != manifest.context.key:
                issues.append(
                    ValidationIssue(
                        "element_context_mismatch",
                        IssueSeverity.ERROR,
                        "Candidate element applicability context differs from the case.",
                        f"candidate_elements[{index}].context",
                        "Select an element whose disease, age, state, territory, and treatment "
                        "phase match the case.",
                    )
                )
            if not element.features:
                issues.append(
                    ValidationIssue(
                        "element_without_features",
                        IssueSeverity.WARNING,
                        "Candidate element has no numeric evidence features.",
                        f"candidate_elements[{index}].features",
                        "Supply measured or explicitly unsupported channel values.",
                    )
                )
        return _report(issues[: limits.max_issues])

    def validate_dossier(self, dossier: Dossier) -> ValidationReport:
        limits, invalid_limits = self._limits_or_report()
        if invalid_limits is not None:
            return invalid_limits
        if limits is None:  # pragma: no cover - paired return invariant above
            raise AssertionError("validated limits missing")
        if type(dossier) is not Dossier:
            return _single_error(
                "invalid_dossier_type",
                "Dossier must be an exact Dossier object.",
                "dossier",
                "Construct the dossier through Dossier.from_dict before validation.",
            )
        try:
            return self._validate_dossier_impl(dossier, limits)
        except _BudgetFailure as error:
            return _single_error(
                "validation_limit_exceeded",
                str(error),
                error.path,
                "Reduce the dossier or lower upstream producer bounds.",
            )
        except _PreflightFailure as error:
            return _single_error(
                error.code,
                str(error),
                error.path,
                "Rehydrate the dossier from its exact canonical typed representation.",
            )
        except Exception as error:  # noqa: BLE001 - public validation must fail closed
            return _single_error(
                "dossier_validation_failed",
                f"Dossier could not be validated safely: {_safe_exception(error)}.",
                "dossier",
                "Rehydrate the dossier from canonical JSON and retry validation.",
            )

    def _validate_dossier_impl(
        self,
        dossier: Dossier,
        limits: ValidationLimits,
    ) -> ValidationReport:
        _dossier_preflight(dossier, limits)
        raw = _canonical_payload(dossier, limits)
        issues = _BoundedIssueList(limits.max_issues)
        canonical_body = {key: value for key, value in raw.items() if key != "content_address"}
        if not _is_sha256_address(dossier.content_address) or (
            dossier.content_address != content_hash(canonical_body)
        ):
            issues.append(
                ValidationIssue(
                    "dossier_address_mismatch",
                    IssueSeverity.ERROR,
                    "Dossier content address does not match its canonical payload.",
                    "content_address",
                    "Rebuild the dossier from its canonical fields before review or release.",
                )
            )
        if not _is_sha256_address(dossier.input_address):
            issues.append(
                _error(
                    "invalid_input_address",
                    "Dossier input address is not a canonical sha256 address.",
                    "input_address",
                    "Bind the dossier to the stored canonical case manifest.",
                )
            )
        if not _is_sha256_address(dossier.event_head):
            issues.append(
                _error(
                    "invalid_event_head",
                    "Dossier event head is not a canonical sha256 address.",
                    "event_head",
                    "Bind the dossier to a verified canonical event-chain head.",
                )
            )
        if not dossier.research_use_only:
            issues.append(
                ValidationIssue(
                    "research_boundary_missing",
                    IssueSeverity.ERROR,
                    "Dossier is missing the research-use-only flag.",
                    "research_use_only",
                    "Do not release the dossier until the boundary is present.",
                )
            )

        bundle_addresses = set(dossier.source_bundle_addresses)
        if len(bundle_addresses) != len(dossier.source_bundle_addresses):
            issues.append(
                _error(
                    "duplicate_source_bundle_address",
                    "Dossier source bundle addresses are not unique.",
                    "source_bundle_addresses",
                    "Persist each source bundle address once.",
                )
            )
        invalid_bundle_addresses = {
            address
            for address in dossier.source_bundle_addresses
            if not _is_sha256_address(address)
        }
        if invalid_bundle_addresses:
            issues.append(
                _error(
                    "invalid_source_bundle_address",
                    "Dossier contains malformed source bundle addresses: "
                    f"{_describe(invalid_bundle_addresses)}.",
                    "source_bundle_addresses",
                    "Use canonical sha256 addresses returned by the object store.",
                )
            )

        parsed_receipts: list[FetchReceipt] = []
        receipts_by_request: dict[str, bytes] = {}
        for index, raw_receipt in enumerate(dossier.source_receipts):
            try:
                receipt = _parse_receipt(raw_receipt)
            except Exception as error:  # noqa: BLE001 - malformed receipts fail closed
                issues.append(
                    _error(
                        "invalid_source_receipt",
                        f"Source receipt is not canonical: {_safe_exception(error)}.",
                        f"source_receipts[{index}]",
                        "Persist the exact FetchReceipt.to_dict representation.",
                    )
                )
                continue
            parsed_receipts.append(receipt)
            fingerprint = canonical_bytes(receipt.to_dict())
            previous_receipt = receipts_by_request.get(receipt.request_hash)
            if previous_receipt is not None and previous_receipt != fingerprint:
                issues.append(
                    _error(
                        "conflicting_source_receipt",
                        "The same source request hash has conflicting receipt definitions.",
                        f"source_receipts[{index}]",
                        "Retain one immutable receipt definition for each exact request.",
                    )
                )
            receipts_by_request[receipt.request_hash] = fingerprint
        if dossier.source_receipts and not dossier.source_bundle_addresses:
            issues.append(
                _error(
                    "source_receipts_without_bundle",
                    "Source receipts are present without an addressed source bundle.",
                    "source_bundle_addresses",
                    "Persist the source bundle and attach its object-store address.",
                )
            )

        external_addresses = {dossier.input_address, *bundle_addresses}
        for receipt in parsed_receipts:
            external_addresses.add(receipt.request_hash)
            if receipt.response_hash is not None:
                external_addresses.add(receipt.response_hash)
        if not dossier.evidence:
            issues.append(
                ValidationIssue(
                    "no_evidence",
                    IssueSeverity.ERROR,
                    "Dossier has no evidence claims.",
                    "evidence",
                    "Return an explicit abstention claim when evidence cannot be collected.",
                )
            )
        hypothesis_ids = [item.hypothesis_id for item in dossier.hypotheses]
        claim_ids = [item.evidence_id for item in dossier.evidence]
        option_ids = [item.option_id for item in dossier.experiments]
        all_edges = [edge for hypothesis in dossier.hypotheses for edge in hypothesis.edges]
        edge_ids = [edge.edge_id for edge in all_edges]
        for values, code, path, label in (
            (hypothesis_ids, "duplicate_hypothesis_id", "hypotheses", "hypothesis IDs"),
            (claim_ids, "duplicate_evidence_id", "evidence", "evidence IDs"),
            (option_ids, "duplicate_experiment_id", "experiments", "experiment IDs"),
        ):
            if len(values) != len(set(values)):
                issues.append(
                    ValidationIssue(
                        code,
                        IssueSeverity.ERROR,
                        f"Dossier contains duplicate {label}.",
                        path,
                        f"Assign a unique stable identifier to every {label[:-1]}.",
                    )
                )

        edges_by_id: dict[str, HypothesisEdge] = {}
        conflicting_edge_ids: set[str] = set()
        for edge in all_edges:
            previous = edges_by_id.get(edge.edge_id)
            if previous is not None and canonical_bytes(previous.to_dict()) != canonical_bytes(
                edge.to_dict()
            ):
                conflicting_edge_ids.add(edge.edge_id)
            edges_by_id[edge.edge_id] = edge
        if conflicting_edge_ids:
            issues.append(
                ValidationIssue(
                    "conflicting_edge_definition",
                    IssueSeverity.ERROR,
                    "Repeated edge IDs have conflicting definitions: "
                    f"{sorted(conflicting_edge_ids)}.",
                    "hypotheses[*].edges",
                    "Reuse an edge ID only when every serialized edge field is identical.",
                )
            )

        claims_by_id = {claim.evidence_id: claim for claim in dossier.evidence}
        known_claim_ids = set(claim_ids)
        known_edge_ids = set(edge_ids)
        evidence_positions: dict[str, int] = {}
        for position, claim in enumerate(dossier.evidence):
            evidence_positions.setdefault(claim.evidence_id, position)
        for index, claim in enumerate(dossier.evidence):
            bad_dependencies: list[str] = []
            undeclared_external: list[str] = []
            for dependency in claim.depends_on:
                dependency_position = evidence_positions.get(dependency)
                if dependency_position is None:
                    if not _is_content_address(dependency):
                        bad_dependencies.append(dependency)
                    elif dependency not in external_addresses:
                        undeclared_external.append(dependency)
                elif dependency_position >= index:
                    bad_dependencies.append(dependency)
            if bad_dependencies:
                issues.append(
                    ValidationIssue(
                        "invalid_evidence_dependency",
                        IssueSeverity.ERROR,
                        "Evidence claim has dangling, forward, or cyclic dependencies: "
                        f"{_describe(bad_dependencies)}.",
                        f"evidence[{index}].depends_on",
                        "Depend only on earlier ledger claims or declared canonical sources.",
                    )
                )
            if undeclared_external:
                issues.append(
                    _error(
                        "undeclared_evidence_dependency",
                        "Evidence claim depends on content not declared by this dossier: "
                        f"{_describe(undeclared_external)}.",
                        f"evidence[{index}].depends_on",
                        "Attach the input, source bundle, or source receipt that owns the address.",
                    )
                )
            if claim.supersedes is not None:
                superseded_index = evidence_positions.get(claim.supersedes)
                if superseded_index is None or superseded_index >= index:
                    issues.append(
                        ValidationIssue(
                            "invalid_evidence_supersession",
                            IssueSeverity.ERROR,
                            "Evidence supersedes a missing, current, or later ledger claim.",
                            f"evidence[{index}].supersedes",
                            "Supersede only an earlier claim in the same evidence ledger.",
                        )
                    )
                elif claims_by_id[claim.supersedes].edge_id != claim.edge_id:
                    issues.append(
                        _error(
                            "cross_edge_evidence_supersession",
                            "Evidence supersedes a claim bound to a different edge.",
                            f"evidence[{index}].supersedes",
                            "Supersede only earlier claims on the exact same typed edge.",
                        )
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
        dossier_context_keys = {hypothesis.context.key for hypothesis in dossier.hypotheses} | {
            claim.context.key for claim in dossier.evidence
        }
        if len(dossier_context_keys) > 1:
            issues.append(
                _error(
                    "mixed_dossier_context",
                    "Hypotheses and evidence do not share one applicability context.",
                    "hypotheses[*].context",
                    "Partition claims into separate dossiers for distinct case contexts.",
                )
            )
        for index, hypothesis in enumerate(dossier.hypotheses):
            hypothesis_claim_ids = {
                claim_id for edge in hypothesis.edges for claim_id in edge.claim_ids
            }
            for edge in hypothesis.edges:
                missing = set(edge.claim_ids) - known_claim_ids
                if missing:
                    issues.append(
                        ValidationIssue(
                            "dangling_claim_reference",
                            IssueSeverity.ERROR,
                            f"Hypothesis edge references unknown claims: {sorted(missing)}.",
                            f"hypotheses[{index}].edges",
                            "Persist every claim before publishing its parent edge.",
                        )
                    )
                mismatched = sorted(
                    claim_id
                    for claim_id in edge.claim_ids
                    if claim_id in claims_by_id and claims_by_id[claim_id].edge_id != edge.edge_id
                )
                if mismatched:
                    issues.append(
                        ValidationIssue(
                            "claim_edge_mismatch",
                            IssueSeverity.ERROR,
                            f"Claims are bound to a different edge: {mismatched}.",
                            f"hypotheses[{index}].edges",
                            "Reference a claim only from the edge named by that claim.",
                        )
                    )
            invalid_missing = tuple(
                claim_id
                for claim_id in hypothesis.missing_evidence
                if claim_id not in hypothesis_claim_ids
                or claim_id not in claims_by_id
                or claims_by_id[claim_id].state not in missing_states
            )
            if invalid_missing:
                issues.append(
                    ValidationIssue(
                        "invalid_missing_evidence",
                        IssueSeverity.ERROR,
                        "Hypothesis has dangling or incorrectly classified missing evidence: "
                        f"{sorted(invalid_missing)}.",
                        f"hypotheses[{index}].missing_evidence",
                        "Name only missing-state claims referenced by this hypothesis.",
                    )
                )
            expected_missing = {
                claim_id
                for claim_id in hypothesis_claim_ids
                if claim_id in claims_by_id and claims_by_id[claim_id].state in missing_states
            }
            omitted_missing = expected_missing - set(hypothesis.missing_evidence)
            if omitted_missing:
                issues.append(
                    _error(
                        "unclassified_missing_evidence",
                        "Hypothesis omits referenced missing-state claims: "
                        f"{_describe(omitted_missing)}.",
                        f"hypotheses[{index}].missing_evidence",
                        "Classify every referenced missing, unsupported, out-of-domain, or "
                        "abstained claim.",
                    )
                )
            invalid_negative = tuple(
                claim_id
                for claim_id in hypothesis.negative_evidence
                if claim_id not in hypothesis_claim_ids
                or claim_id not in claims_by_id
                or claims_by_id[claim_id].state not in negative_states
            )
            if invalid_negative:
                issues.append(
                    ValidationIssue(
                        "invalid_negative_evidence",
                        IssueSeverity.ERROR,
                        "Hypothesis has dangling or incorrectly classified negative evidence: "
                        f"{sorted(invalid_negative)}.",
                        f"hypotheses[{index}].negative_evidence",
                        "Name only negative-state claims referenced by this hypothesis.",
                    )
                )
            expected_negative = {
                claim_id
                for claim_id in hypothesis_claim_ids
                if claim_id in claims_by_id and claims_by_id[claim_id].state in negative_states
            }
            omitted_negative = expected_negative - set(hypothesis.negative_evidence)
            if omitted_negative:
                issues.append(
                    _error(
                        "unclassified_negative_evidence",
                        "Hypothesis omits referenced negative claims: "
                        f"{_describe(omitted_negative)}.",
                        f"hypotheses[{index}].negative_evidence",
                        "Classify every referenced measured-negative or contradictory claim.",
                    )
                )
            unknown_provenance = {
                item
                for item in hypothesis.provenance
                if _is_content_address(item) and item not in external_addresses
            }
            if dossier.input_address not in hypothesis.provenance:
                issues.append(
                    _error(
                        "missing_input_provenance",
                        "Hypothesis provenance does not name the dossier input address.",
                        f"hypotheses[{index}].provenance",
                        "Include the exact canonical case-manifest address in every hypothesis.",
                    )
                )
            if unknown_provenance:
                issues.append(
                    _error(
                        "undeclared_hypothesis_provenance",
                        "Hypothesis provenance names undeclared content: "
                        f"{_describe(unknown_provenance)}.",
                        f"hypotheses[{index}].provenance",
                        "Attach every addressed provenance object to the dossier.",
                    )
                )
            try:
                Dossier._validate_hypothesis_path(hypothesis)
            except ValidationError as exc:
                issues.append(
                    ValidationIssue(
                        "hypothesis_path_identity_mismatch",
                        IssueSeverity.ERROR,
                        str(exc),
                        f"hypotheses[{index}].edges",
                        "Persist the typed edges matching the hypothesis identity path.",
                    )
                )
            if hypothesis.support == 0 and not hypothesis.missing_evidence:
                issues.append(
                    ValidationIssue(
                        "zero_support_without_reason",
                        IssueSeverity.WARNING,
                        "Zero-support hypothesis has no missing-evidence reason.",
                        f"hypotheses[{index}]",
                        "Record unsupported or abstained claims explicitly.",
                    )
                )
            causal_edges = [
                edge
                for edge in hypothesis.edges
                if edge.edge_type is EdgeType.CAUSAL_PATH
                and edge.source_id == hypothesis.variant_id
                and edge.target_id in {hypothesis.state_id, "unresolved"}
            ]
            if len(causal_edges) == 1:
                causal_edge = causal_edges[0]
                if hypothesis.support != causal_edge.support:
                    issues.append(
                        _error(
                            "hypothesis_support_mismatch",
                            "Hypothesis support does not equal its causal-path edge support.",
                            f"hypotheses[{index}].support",
                            "Recompute the hypothesis from its closed evidence graph.",
                        )
                    )
                if hypothesis.uncertainty < causal_edge.uncertainty:
                    issues.append(
                        _error(
                            "hypothesis_uncertainty_mismatch",
                            "Hypothesis uncertainty is lower than its causal-path uncertainty.",
                            f"hypotheses[{index}].uncertainty",
                            "Retain at least the uncertainty of the causal-path aggregate.",
                        )
                    )
        evidence_graph: EvidenceGraph | None = None
        if len(known_claim_ids) == len(claim_ids):
            try:
                evidence_graph = EvidenceGraph(
                    limits=EvidenceGraphLimits(
                        max_claims=limits.max_evidence_claims,
                        max_claims_per_edge=limits.max_claims_per_edge,
                        max_dependencies_per_claim=limits.max_dependencies_per_claim,
                        max_claim_bytes=min(limits.max_canonical_bytes, 16 * 1024 * 1024),
                        max_graph_bytes=min(limits.max_canonical_bytes, 128 * 1024 * 1024),
                    )
                )
                evidence_graph.extend(dossier.evidence)
            except Exception as error:  # noqa: BLE001 - malformed graphs fail closed
                issues.append(
                    _error(
                        "invalid_evidence_graph",
                        f"Evidence graph is not canonical and closed: {_safe_exception(error)}.",
                        "evidence",
                        "Rebuild claims through the bounded EvidenceGraph API.",
                    )
                )
                evidence_graph = None
        if evidence_graph is not None and not conflicting_edge_ids:
            for edge_id in sorted(edges_by_id):
                edge = edges_by_id[edge_id]
                try:
                    aggregate = evidence_graph.aggregate(edge)
                except Exception as error:  # noqa: BLE001 - malformed edges fail closed
                    issues.append(
                        _error(
                            "invalid_edge_aggregate",
                            f"Edge aggregate could not be verified: {_safe_exception(error)}.",
                            "hypotheses[*].edges",
                            "Recompute the edge from claims bound to its exact typed identity.",
                        )
                    )
                    continue
                expected_ids = (
                    aggregate.supported_claim_ids
                    + aggregate.negative_claim_ids
                    + aggregate.missing_claim_ids
                )
                if (
                    edge.support != aggregate.score
                    or edge.uncertainty != aggregate.uncertainty
                    or edge.context_fit != aggregate.context_support
                    or edge.support_level is not _support_level(aggregate.score)
                    or edge.claim_ids != expected_ids
                ):
                    issues.append(
                        _error(
                            "edge_aggregate_mismatch",
                            f"Edge {edge.edge_id!r} does not match its active evidence aggregate.",
                            "hypotheses[*].edges",
                            "Rebuild edge scores, classifications, and claim order from "
                            "EvidenceGraph.aggregate.",
                        )
                    )

        for index, experiment in enumerate(dossier.experiments):
            missing_edges = set(experiment.tests_edges) - known_edge_ids
            if missing_edges:
                issues.append(
                    ValidationIssue(
                        "dangling_experiment_edge",
                        IssueSeverity.ERROR,
                        f"Experiment references unknown edges: {sorted(missing_edges)}.",
                        f"experiments[{index}].tests_edges",
                        "Target only edges persisted in this dossier.",
                    )
                )
        if dossier.review is not None:
            if dossier.review.case_id != dossier.case_id:
                issues.append(
                    ValidationIssue(
                        "review_case_mismatch",
                        IssueSeverity.ERROR,
                        "Review case does not match the dossier case.",
                        "review.case_id",
                        "Attach only a review created for this dossier case.",
                    )
                )
            unknown_hypotheses = set(dossier.review.reviewed_hypothesis_ids) - set(hypothesis_ids)
            if unknown_hypotheses:
                issues.append(
                    ValidationIssue(
                        "review_unknown_hypothesis",
                        IssueSeverity.ERROR,
                        f"Review names unknown hypotheses: {sorted(unknown_hypotheses)}.",
                        "review.reviewed_hypothesis_ids",
                        "Review only hypotheses present in this dossier snapshot.",
                    )
                )
            unknown_claims = set(dossier.review.checked_claim_ids) - known_claim_ids
            if unknown_claims:
                issues.append(
                    ValidationIssue(
                        "review_unknown_claim",
                        IssueSeverity.ERROR,
                        f"Review names unknown evidence claims: {sorted(unknown_claims)}.",
                        "review.checked_claim_ids",
                        "Check only evidence present in this dossier snapshot.",
                    )
                )
            if (
                dossier.review.state is ReviewState.ACCEPTED
                and dossier.status is not ResearchStatus.RELEASED_RESEARCH
            ):
                issues.append(
                    _error(
                        "acceptance_without_release",
                        "An accepted review is attached to a non-released dossier.",
                        "status",
                        "Use released_research for an accepted snapshot or attach a non-accepted "
                        "review state.",
                    )
                )
        if dossier.status is ResearchStatus.REVIEWED and dossier.review is None:
            issues.append(
                _error(
                    "reviewed_without_decision",
                    "Reviewed dossier has no review decision.",
                    "review",
                    "Attach the review decision that produced the reviewed status.",
                )
            )
        if dossier.status is ResearchStatus.RELEASED_RESEARCH:
            if dossier.review is None or dossier.review.state is not ReviewState.ACCEPTED:
                issues.append(
                    ValidationIssue(
                        "release_without_acceptance",
                        IssueSeverity.ERROR,
                        "Released dossier is not backed by an accepted review.",
                        "review",
                        "Record an accepted review that names the hypotheses and checked claims.",
                    )
                )
            else:
                unreviewed_hypotheses = set(hypothesis_ids) - set(
                    dossier.review.reviewed_hypothesis_ids
                )
                unchecked_claims = known_claim_ids - set(dossier.review.checked_claim_ids)
                if unreviewed_hypotheses:
                    issues.append(
                        _error(
                            "incomplete_hypothesis_review",
                            "Accepted release review omits hypotheses: "
                            f"{_describe(unreviewed_hypotheses)}.",
                            "review.reviewed_hypothesis_ids",
                            "Review every hypothesis in the released immutable snapshot.",
                        )
                    )
                if unchecked_claims:
                    issues.append(
                        _error(
                            "incomplete_claim_review",
                            "Accepted release review omits evidence claims: "
                            f"{_describe(unchecked_claims)}.",
                            "review.checked_claim_ids",
                            "Check every evidence claim in the released immutable snapshot.",
                        )
                    )
            if any(claim.state is EvidenceState.ABSTAINED for claim in dossier.evidence):
                issues.append(
                    ValidationIssue(
                        "released_abstention",
                        IssueSeverity.WARNING,
                        "Released dossier contains abstained evidence.",
                        "evidence[*].state",
                        "Keep the abstention visible and document why the dossier remains useful.",
                    )
                )
        try:
            canonical = Dossier.from_dict(raw)
            if canonical_bytes(canonical.to_dict()) != canonical_bytes(raw):
                raise ValidationError("dossier does not round-trip exactly")
        except Exception as error:  # noqa: BLE001 - malformed typed snapshots fail closed
            issues.append(
                _error(
                    "noncanonical_dossier",
                    "Dossier is not an exact canonical typed representation: "
                    f"{_safe_exception(error)}.",
                    "dossier",
                    "Rebuild the dossier through Dossier.from_dict before release.",
                )
            )
        return _report(issues[: limits.max_issues])


class ReleaseGate:
    """Fail-closed structural and policy checks for one release snapshot."""

    def __init__(
        self,
        policy: ResearchPolicy | None = None,
        *,
        limits: ValidationLimits | None = None,
    ) -> None:
        selected_policy = ResearchPolicy() if policy is None else policy
        if type(selected_policy) is not ResearchPolicy:
            raise ValidationError("policy must be an exact ResearchPolicy")
        self.policy = selected_policy
        self.validator = ContractValidator(limits=limits)

    def check(self, dossier: Dossier) -> ValidationReport:
        if type(self.validator) is not ContractValidator:
            return _single_error(
                "invalid_release_validator",
                "Release gate validator is not an exact ContractValidator.",
                "release_gate.validator",
                "Restore the gate's bounded ContractValidator before checking release.",
            )
        structural = self.validator.validate_dossier(dossier)
        if not structural.valid:
            return structural
        if type(dossier) is not Dossier:  # pragma: no cover - structural check narrows this
            return structural
        limits, invalid_limits = self.validator._limits_or_report()
        if invalid_limits is not None:
            return invalid_limits
        if limits is None:  # pragma: no cover - paired return invariant above
            raise AssertionError("validated limits missing")
        issues = _BoundedIssueList(limits.max_issues)
        issues.extend(structural.issues)
        if dossier.status is not ResearchStatus.RELEASED_RESEARCH:
            issues.append(
                _error(
                    "release_status_required",
                    "Release gate requires a released_research dossier snapshot.",
                    "status",
                    "Complete review and create the immutable released snapshot before gating.",
                )
            )
        if type(self.policy) is not ResearchPolicy:
            issues.append(
                _error(
                    "invalid_release_policy",
                    "Release gate policy is not an exact ResearchPolicy.",
                    "release_gate.policy",
                    "Restore the canonical research policy before checking release.",
                )
            )
            return _report(issues[: limits.max_issues])
        try:
            policy = self.policy.validate_dossier(dossier)
        except Exception as error:  # noqa: BLE001 - release checks must fail closed
            issues.append(
                _error(
                    "policy_evaluation_failed",
                    f"Research policy could not be evaluated safely: {_safe_exception(error)}.",
                    "policy",
                    "Restore the canonical policy configuration and retry.",
                )
            )
            return _report(issues[: limits.max_issues])
        if type(policy) is not PolicyDecision:
            issues.append(
                _error(
                    "invalid_policy_decision",
                    "Research policy returned a non-canonical decision.",
                    "policy",
                    "Use the canonical ResearchPolicy implementation.",
                )
            )
            return _report(issues[: limits.max_issues])
        issues.extend(
            _error(
                "policy_violation",
                violation[:16_384],
                "policy",
                "Remove the prohibited claim or keep the dossier unreleased.",
            )
            for violation in policy.violations
        )
        return _report(issues[: limits.max_issues])
