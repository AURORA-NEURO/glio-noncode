"""Typed in-memory case preparation and execution.

This module is the small, fail-closed facade over variant intake, regulatory
track intake, ``CaseManifest``, and ``CaseRuntime``.  Source payloads are
always supplied by the caller; this boundary never resolves a server-local
path.  Observational timestamps are retained on stage receipts but are
deliberately excluded from every scientific content address.
"""

from __future__ import annotations

import base64
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
from .intake import IntakeBatch, IntakeFormat, IntakeSeverity, VariantIntake
from .models import CandidateElement, CaseManifest, Dossier, ReferenceContext
from .regulatory_tracks import (
    RegulatoryTrackBatch,
    RegulatoryTrackFormat,
    RegulatoryTrackParser,
    TrackIssueSeverity,
)
from .replay import ReplayReport, ReplayVerifier
from .runtime import CaseRuntime
from .serialization import content_hash, hash_bytes, jsonable, utc_now

WORKFLOW_VERSION = "case-workflow-v1"
MAX_CASE_RNA_CONSEQUENCES = 10_000
MAX_CASE_REGULATORY_TRACKS = 1_000
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


def _required_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{label} must not be empty")
    return value.strip()


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


def _json_mapping(value: Mapping[str, Any] | None, label: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValidationError(f"{label} must be an object")
    result = dict(value)
    try:
        content_hash(result)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{label} must contain JSON-compatible values") from exc
    return result


def _context(value: ReferenceContext | Mapping[str, Any], label: str) -> ReferenceContext:
    if isinstance(value, ReferenceContext):
        return value
    raw = _strict_mapping(value, allowed=_CONTEXT_FIELDS, label=label)
    return ReferenceContext.from_dict(raw)


def _verify_address(raw: Mapping[str, Any], actual: str, label: str) -> None:
    supplied = raw.get("content_address")
    if supplied is not None and str(supplied) != actual:
        raise ValidationError(f"{label} content_address does not match its canonical payload")


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
    for index, item in enumerate(_sequence(raw["variants"], "prepared manifest variants")):
        if not isinstance(item, Mapping):
            raise ValidationError(f"prepared manifest variant {index} must be an object")
        _strict_mapping(
            item,
            allowed=_VARIANT_FIELDS,
            required=_VARIANT_FIELDS,
            label=f"prepared manifest variant {index}",
        )
    for index, item in enumerate(
        _sequence(raw.get("candidate_elements", ()), "prepared manifest candidate_elements")
    ):
        if not isinstance(item, Mapping):
            raise ValidationError(f"prepared manifest candidate element {index} must be an object")
        element_raw = _strict_mapping(
            item,
            allowed=_ELEMENT_FIELDS,
            required=_ELEMENT_FIELDS,
            label=f"prepared manifest candidate element {index}",
        )
        element_context = element_raw.get("context")
        if element_context is not None:
            if not isinstance(element_context, Mapping):
                raise ValidationError(
                    f"prepared manifest candidate element {index} context must be an object"
                )
            _strict_mapping(
                element_context,
                allowed=_CONTEXT_FIELDS,
                required=_CONTEXT_FIELDS,
                label=f"prepared manifest candidate element {index} context",
            )
    return CaseManifest.from_dict(raw)


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
            normalized.append(RNAConsequenceEvidence.from_mapping(item.to_dict()))
            continue
        if not isinstance(item, Mapping):
            raise ValidationError(
                f"rna_consequences item {index} must be RNAConsequenceEvidence or an object"
            )
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
        raise ValidationError(
            f"{label} exceeds the maximum of {MAX_CASE_REGULATORY_TRACKS} tracks"
        )
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
    value = raw[candidates[0]]
    encoding = str(raw.get("payload_encoding", raw.get("data_encoding", "text")))
    if not isinstance(value, str):
        raise ValidationError(f"{label} payload must be a string")
    if encoding == "text":
        return value
    if encoding != "base64":
        raise ValidationError(f"{label} payload encoding must be text or base64")
    try:
        return base64.b64decode(value.encode("ascii"), validate=True)
    except (ValueError, UnicodeEncodeError) as exc:
        raise ValidationError(f"{label} payload is not valid base64") from exc


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
        try:
            selected = IntakeFormat(str(self.input_format))
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
            source_id=str(raw["source_id"]),
            input_format=str(selected_format),
            genome_build=str(raw["genome_build"]),
            payload=_decoded_mapping_payload(raw, "variant source"),
            sample_id=None if raw.get("sample_id") is None else str(raw["sample_id"]),
            include_no_call=include_no_call,
            metadata=_json_mapping(raw.get("metadata"), "variant metadata"),
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
        try:
            selected = RegulatoryTrackFormat(str(self.input_format))
        except ValueError as exc:
            raise ValidationError(
                f"unsupported regulatory track format: {self.input_format}"
            ) from exc
        object.__setattr__(self, "input_format", selected)
        object.__setattr__(self, "context", _context(self.context, "track context"))
        if not isinstance(self.payload, (str, bytes)):
            raise ValidationError("regulatory track payload must be text or bytes")
        object.__setattr__(self, "metadata", _json_mapping(self.metadata, "track metadata"))
        keys = tuple(
            _required_text(item, "target_gene_keys item") for item in self.target_gene_keys
        )
        if not keys or len(keys) != len(set(keys)):
            raise ValidationError("target_gene_keys must be a non-empty unique sequence")
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
        keys = tuple(str(item) for item in _sequence(keys_raw, "target_gene_keys"))
        return cls(
            source_id=str(raw["source_id"]),
            input_format=str(selected_format),
            genome_build=str(raw["genome_build"]),
            context=context_raw,
            payload=_decoded_mapping_payload(raw, "regulatory track source"),
            metadata=_json_mapping(raw.get("metadata"), "track metadata"),
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
        object.__setattr__(self, "severity", WorkflowSeverity(str(self.severity)))
        object.__setattr__(self, "stage", WorkflowStage(str(self.stage)))
        if self.source_id is not None:
            object.__setattr__(self, "source_id", _required_text(self.source_id, "source_id"))
        if self.line_number is not None and self.line_number < 1:
            raise ValidationError("issue line_number must be positive")

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
            code=str(raw["code"]),
            severity=str(raw["severity"]),
            stage=str(raw["stage"]),
            message=str(raw["message"]),
            source_id=None if raw.get("source_id") is None else str(raw["source_id"]),
            line_number=None if line is None else int(line),
            raw_hash=None if raw.get("raw_hash") is None else str(raw["raw_hash"]),
            remediation=str(raw["remediation"]),
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
        object.__setattr__(self, "stage", WorkflowStage(str(self.stage)))
        object.__setattr__(self, "state", WorkflowState(str(self.state)))
        object.__setattr__(self, "source_id", _required_text(self.source_id, "receipt source_id"))
        object.__setattr__(
            self, "input_address", _required_text(self.input_address, "input_address")
        )
        object.__setattr__(self, "observed_at", _required_text(self.observed_at, "observed_at"))
        if self.output_address is not None:
            object.__setattr__(
                self, "output_address", _required_text(self.output_address, "output_address")
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
        object.__setattr__(
            self, "issue_addresses", tuple(str(item) for item in self.issue_addresses)
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
            stage=str(raw["stage"]),
            state=str(raw["state"]),
            source_id=str(raw["source_id"]),
            input_address=str(raw["input_address"]),
            output_address=(
                None if raw.get("output_address") is None else str(raw["output_address"])
            ),
            observed_at=str(raw["observed_at"]),
            record_count=int(raw["record_count"]),
            accepted_count=int(raw["accepted_count"]),
            rejected_count=int(raw["rejected_count"]),
            warning_count=int(raw["warning_count"]),
            error_count=int(raw["error_count"]),
            issue_addresses=tuple(
                str(item) for item in _sequence(raw["issue_addresses"], "issue_addresses")
            ),
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
        object.__setattr__(self, "state", WorkflowState(str(self.state)))
        if type(self.live_reference) is not bool:
            raise ValidationError("live_reference must be a boolean")
        object.__setattr__(self, "stage_receipts", tuple(self.stage_receipts))
        object.__setattr__(self, "issues", tuple(self.issues))
        if self.accepted:
            if self.manifest is None or not self.run_id:
                raise ValidationError("accepted preparation requires a manifest and run_id")
            if any(issue.severity == WorkflowSeverity.ERROR for issue in self.issues):
                raise ValidationError("accepted preparation cannot contain error issues")
            expected = _run_id(self.manifest)
            if self.run_id != expected:
                raise ValidationError("prepared run_id does not match the manifest identity")
        elif self.manifest is not None or self.run_id is not None:
            raise ValidationError("blocked preparation must not expose an executable manifest")

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
            state=str(raw["state"]),
            manifest=manifest,
            run_id=None if raw["run_id"] is None else str(raw["run_id"]),
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
        object.__setattr__(self, "state", WorkflowState(str(self.state)))
        object.__setattr__(self, "stage_receipts", tuple(self.stage_receipts))
        object.__setattr__(self, "issues", tuple(self.issues))
        if self.run_record is not None:
            object.__setattr__(self, "run_record", _json_mapping(self.run_record, "run record"))
        if self.accepted:
            if not self.prepared.accepted:
                raise ValidationError("an accepted run requires accepted preparation")
            if self.dossier is None or self.run_record is None or self.replay_report is None:
                raise ValidationError(
                    "an accepted run requires a dossier, run record, and replay report"
                )
            if any(issue.severity == WorkflowSeverity.ERROR for issue in self.issues):
                raise ValidationError("accepted run cannot contain error issues")

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
        dossier = None
        if dossier_raw is not None:
            strict_dossier = _strict_mapping(
                dossier_raw,
                allowed=_DOSSIER_FIELDS,
                required=_DOSSIER_FIELDS,
                label="run result dossier",
            )
            dossier = Dossier.from_dict(strict_dossier)
            dossier_payload = {
                key: item for key, item in dossier_raw.items() if key != "content_address"
            }
            assert dossier is not None
            if content_hash(dossier_payload) != dossier.content_address:
                raise ValidationError(
                    "dossier content_address does not match its canonical payload"
                )
        run_raw = raw["run_record"]
        if run_raw is not None and not isinstance(run_raw, Mapping):
            raise ValidationError("run_record must be an object or null")
        replay_raw = raw["replay_report"]
        replay = None if replay_raw is None else _replay_from_mapping(replay_raw)
        result = cls(
            state=str(raw["state"]),
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
        run_id=str(raw["run_id"]),
        event_chain_valid=raw["event_chain_valid"],
        input_address=str(raw["input_address"]),
        dossier_address=str(raw["dossier_address"]),
        stored_dossier_matches_address=raw["stored_dossier_matches_address"],
        warnings=tuple(str(item) for item in _sequence(raw["warnings"], "replay warnings")),
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
    return content_hash(
        {
            "version": WORKFLOW_VERSION,
            "batch_address": batch.content_address,
            "context": source.context.to_dict(),
            "source_metadata": jsonable(dict(source.metadata)),
            "target_gene_keys": list(source.target_gene_keys),
            "candidate_elements": [item.to_dict() for item in elements],
        }
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
    user_metadata = _json_mapping(metadata, "case metadata")
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
        try:
            batch, elements = _parse_track(track)
            track_gate.extend(_track_issues(batch))
            candidates.extend(elements)
        except (GlioError, UnicodeError, ValueError, TypeError) as exc:
            track_gate.append(
                WorkflowIssue(
                    code="regulatory_track_error",
                    severity=WorkflowSeverity.ERROR,
                    stage=WorkflowStage.REGULATORY_TRACK,
                    message=str(exc),
                    source_id=track.source_id,
                    remediation="Correct the inline track payload and its explicit metadata.",
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
        sorted(
            candidates,
            key=lambda item: (
                item.element_id,
                item.source_id,
                item.chromosome,
                item.start,
                item.end,
            ),
        )
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
            manifest = CaseManifest(
                case_id=case_id,
                subject_id=subject_id,
                context=case_context,
                variants=variants,
                candidate_elements=candidates_tuple,
                metadata=manifest_metadata,
                input_versions=dict(sorted(input_versions.items())),
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

    value = prepared if isinstance(prepared, PreparedCase) else PreparedCase.from_mapping(prepared)
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

    if (
        not value.accepted
        or value.manifest is None
        or value.run_id is None
        or rna_input_blocked
    ):
        blocked_metadata: dict[str, Any] = {
            "executed": False,
            "reason": (
                "invalid_rna_consequence" if rna_input_blocked else "preparation_blocked"
            ),
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


def variant_source_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "urn:glio-noncode:case-workflow:variant-source:v1",
        "type": "object",
        "additionalProperties": False,
        "required": ["source_id", "input_format", "genome_build", "payload"],
        "properties": {
            "source_id": {"type": "string", "minLength": 1},
            "input_format": {"enum": [item.value for item in IntakeFormat]},
            "genome_build": {"type": "string", "minLength": 1},
            "payload": {"type": "string"},
            "payload_encoding": {"enum": ["text", "base64"], "default": "text"},
            "sample_id": {"type": ["string", "null"]},
            "include_no_call": {"type": "boolean", "default": False},
            "metadata": {"type": "object"},
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
            "source_id": {"type": "string", "minLength": 1},
            "input_format": {"enum": [item.value for item in RegulatoryTrackFormat]},
            "genome_build": {"type": "string", "minLength": 1},
            "context": {
                "type": "object",
                "additionalProperties": False,
                "required": ["genome_build", "disease_class", "age_group", "cell_state"],
                "properties": {
                    "genome_build": {"type": "string", "minLength": 1},
                    "disease_class": {"type": "string", "minLength": 1},
                    "age_group": {"type": "string", "minLength": 1},
                    "cell_state": {"type": "string", "minLength": 1},
                    "territory": {"type": "string"},
                    "treatment_phase": {"type": "string"},
                    "assay_support": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "source_version": {"type": "string"},
                },
            },
            "payload": {"type": "string"},
            "payload_encoding": {"enum": ["text", "base64"], "default": "text"},
            "metadata": {"type": "object"},
            "target_gene_keys": {
                "type": "array",
                "minItems": 1,
                "uniqueItems": True,
                "items": {"type": "string", "minLength": 1},
            },
        },
    }


def prepared_case_schema() -> dict[str, Any]:
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
            "manifest": {"type": ["object", "null"]},
            "manifest_address": {"type": ["string", "null"]},
            "run_id": {"type": ["string", "null"]},
            "live_reference": {"type": "boolean"},
            "stage_receipts": {"type": "array", "items": {"type": "object"}},
            "issues": {"type": "array", "items": {"type": "object"}},
            "content_address": {"type": "string", "pattern": "^sha256:[0-9a-f]{64}$"},
        },
    }


def run_result_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "urn:glio-noncode:case-workflow:run-result:v1",
        "type": "object",
        "additionalProperties": False,
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
            "prepared": prepared_case_schema(),
            "dossier": {"type": ["object", "null"]},
            "run_record": {"type": ["object", "null"]},
            "replay_report": {"type": ["object", "null"]},
            "stage_receipts": {"type": "array", "items": {"type": "object"}},
            "issues": {"type": "array", "items": {"type": "object"}},
            "content_address": {"type": "string", "pattern": "^sha256:[0-9a-f]{64}$"},
        },
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
                "predicted_direction": {
                    "enum": [item.value for item in RegulatoryDirection]
                },
                "state": {"enum": [item.value for item in RNAEvidenceState]},
                "expression_state": {
                    "enum": [None, *(item.value for item in RNAEvidenceState)]
                },
                "expression_direction": {
                    "enum": [None, *(item.value for item in ExpressionDirection)]
                },
                "expression_robust_z": {"type": ["number", "null"]},
                "expression_result_address": {"type": ["string", "null"]},
                "allelic_state": {
                    "enum": [None, *(item.value for item in RNAEvidenceState)]
                },
                "allelic_direction": {
                    "enum": [None, *(item.value for item in AllelicDirection)]
                },
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
                    "items": {"type": "string"},
                },
                "content_address": {
                    "type": "string",
                    "pattern": "^rna-consequence-evidence:[0-9a-f]{64}$",
                },
            },
        },
    }


def case_workflow_schema() -> dict[str, Any]:
    """Return the complete inline-source facade contract."""

    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "urn:glio-noncode:case-workflow:v1",
        "version": WORKFLOW_VERSION,
        "type": "object",
        "additionalProperties": False,
        "$defs": {
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
            "regulatory_tracks": {
                "max_items": MAX_CASE_REGULATORY_TRACKS,
                "canonical_order": "source identity and canonical content",
            }
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
            "invalid_rna_consequence",
            "replay_integrity_error",
        ],
        "persistence": "CaseRuntime content-addressed dossier and event replay",
        "schemas": {
            "workflow": case_workflow_schema()["$id"],
            "variant_source": variant_source_schema()["$id"],
            "regulatory_track_source": regulatory_track_source_schema()["$id"],
            "prepared_case": prepared_case_schema()["$id"],
            "run_result": run_result_schema()["$id"],
            "rna_consequence_execution_input": _rna_consequence_execution_input_schema()[
                "$id"
            ],
        },
    }


# Predictable aliases for clients that use module-qualified naming.
workflow_schema = case_workflow_schema
case_workflow_capabilities = capabilities


__all__ = [
    "MAX_CASE_REGULATORY_TRACKS",
    "MAX_CASE_RNA_CONSEQUENCES",
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
    "prepared_case_schema",
    "regulatory_track_source_schema",
    "run_case",
    "run_result_schema",
    "variant_source_schema",
    "workflow_schema",
]
