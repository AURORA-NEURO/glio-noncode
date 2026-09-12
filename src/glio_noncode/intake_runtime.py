"""Typed orchestration runtime for the Domain 01 intake control path.

The individual C13-C16 adapters are useful on their own, but a real intake
workflow needs a single batch boundary that applies them in order and carries
the weakest state forward.  This module provides that boundary without
claiming to replace institutional consent review or laboratory quality
systems.

The pipeline deliberately uses the existing adapters rather than reimplementing
their rules.  It attaches policy, quarantines malformed rows, scores field
coverage, intersects the accepted ID sets, and exports only the rows that pass
all three gates.  If any input row is left behind, the pipeline state remains
``review`` even when a partial manifest can be constructed.  If no row can be
exported, the pipeline state is ``blocked`` and no publication bundle is
reported.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .frontier_data_alpha import (
    ConsentPolicyAttacher,
    DataCompletenessScorer,
    InputAnomalyQuarantine,
    IntakeBundle,
    IntakeBundleExporter,
)
from .serialization import content_hash, jsonable, require_non_empty


class IntakePipelineState(StrEnum):
    """Aggregate state propagated by the ordered intake stages."""

    ACCEPTED = "accepted"
    REVIEW = "review"
    BLOCKED = "blocked"


_MAX_PIPELINE_RECORDS = 100_000
_MAX_PIPELINE_SOURCES = 256
_MAX_PIPELINE_FIELDS = 512
_MAX_PIPELINE_USES = 128
_REQUEST_FIELDS = frozenset(
    {
        "request_id",
        "bundle_id",
        "context_key",
        "policy_id",
        "policy_version",
        "purpose",
        "permitted_uses",
        "records",
        "policy_source_id",
        "source_ids",
        "required_fields",
        "weights",
        "minimum_score",
        "allowed_bases",
        "require_accepted",
    }
)
_REPORT_STAGE_IDS = ("consent", "anomaly", "completeness", "export")
_ADDRESS_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class IntakePipelineRequest:
    """Validated batch input for the four-stage intake runtime."""

    request_id: str
    bundle_id: str
    context_key: str
    policy_id: str
    policy_version: str
    purpose: str
    permitted_uses: tuple[str, ...]
    records: tuple[Mapping[str, Any], ...]
    policy_source_id: str
    source_ids: tuple[str, ...]
    required_fields: tuple[str, ...]
    weights: Mapping[str, float]
    minimum_score: float
    allowed_bases: str
    require_accepted: bool = True

    def __post_init__(self) -> None:
        for field_name in (
            "request_id",
            "bundle_id",
            "context_key",
            "policy_id",
            "policy_version",
            "purpose",
            "policy_source_id",
            "allowed_bases",
        ):
            require_non_empty(getattr(self, field_name), field_name)
        if not isinstance(self.permitted_uses, Sequence) or isinstance(self.permitted_uses, (str, bytes)):
            raise ValidationError("permitted_uses must be an array")
        if not self.permitted_uses:
            raise ValidationError("permitted_uses must not be empty")
        if len(self.permitted_uses) > _MAX_PIPELINE_USES:
            raise ValidationError("permitted_uses exceeds its bound")
        for value in self.permitted_uses:
            require_non_empty(value, "permitted_use")
        if not self.records:
            raise ValidationError("records must not be empty")
        if len(self.records) > _MAX_PIPELINE_RECORDS:
            raise ValidationError("records exceeds its bound")
        if not isinstance(self.source_ids, Sequence) or isinstance(self.source_ids, (str, bytes)):
            raise ValidationError("source_ids must be an array")
        if not self.source_ids:
            raise ValidationError("source_ids must not be empty")
        if len(self.source_ids) > _MAX_PIPELINE_SOURCES:
            raise ValidationError("source_ids exceeds its bound")
        for value in self.source_ids:
            require_non_empty(value, "source_id")
        if not isinstance(self.required_fields, Sequence) or isinstance(self.required_fields, (str, bytes)):
            raise ValidationError("required_fields must be an array")
        if not self.required_fields:
            raise ValidationError("required_fields must not be empty")
        if len(self.required_fields) > _MAX_PIPELINE_FIELDS:
            raise ValidationError("required_fields exceeds its bound")
        for value in self.required_fields:
            require_non_empty(value, "required_field")
        if len(self.required_fields) != len(set(self.required_fields)):
            raise ValidationError("required_fields must be unique")
        if isinstance(self.minimum_score, bool) or not isinstance(self.minimum_score, (int, float)) or not math.isfinite(float(self.minimum_score)):
            raise ValidationError("minimum_score must be finite numeric")
        if self.minimum_score < 0.0 or self.minimum_score > 1.0:
            raise ValidationError("minimum_score must be between 0 and 1")
        if not isinstance(self.weights, Mapping):
            raise ValidationError("weights must be an object")
        if len(self.weights) > _MAX_PIPELINE_FIELDS:
            raise ValidationError("weights exceeds its bound")
        for key, value in self.weights.items():
            require_non_empty(key, "weight field")
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) or float(value) <= 0:
                raise ValidationError("weights must be positive finite numbers")
        if not isinstance(self.require_accepted, bool):
            raise ValidationError("require_accepted must be boolean")
        record_ids: list[str] = []
        for index, row in enumerate(self.records, start=1):
            if not isinstance(row, Mapping):
                raise ValidationError(f"records[{index - 1}] must be an object")
            record_id = row.get("record_id", row.get("id", ""))
            if not isinstance(record_id, str) or not record_id.strip():
                raise ValidationError(f"records[{index - 1}] requires record_id")
            record_ids.append(record_id.strip())
        if len(record_ids) != len(set(record_ids)):
            raise ValidationError("records must have unique record_id values")
        if len(self.source_ids) != len(set(self.source_ids)):
            raise ValidationError("source_ids must be unique")
        if set(self.required_fields) != set(self.weights):
            raise ValidationError("weights must declare exactly the required fields")
        if any(float(value) <= 0 for value in self.weights.values()):
            raise ValidationError("weights must be positive")

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> IntakePipelineRequest:
        """Parse one CLI/API request with explicit defaults only."""

        if not isinstance(raw, Mapping):
            raise ValidationError("intake pipeline request must be an object")
        unknown = set(raw) - _REQUEST_FIELDS
        if unknown:
            raise ValidationError(
                f"intake pipeline request contains unknown fields: {sorted(unknown)}"
            )
        records_raw = raw.get("records", ())
        if not isinstance(records_raw, Sequence) or isinstance(records_raw, (str, bytes)):
            raise ValidationError("intake pipeline records must be an array")
        records: list[Mapping[str, Any]] = []
        for index, row in enumerate(records_raw):
            if not isinstance(row, Mapping):
                raise ValidationError(f"intake pipeline records[{index}] must be an object")
            records.append(dict(row))
        uses_raw = raw.get("permitted_uses", ())
        if not isinstance(uses_raw, Sequence) or isinstance(uses_raw, (str, bytes)):
            raise ValidationError("intake pipeline permitted_uses must be an array")
        fields_raw = raw.get("required_fields", ())
        if not isinstance(fields_raw, Sequence) or isinstance(fields_raw, (str, bytes)):
            raise ValidationError("intake pipeline required_fields must be an array")
        fields = tuple(str(item) for item in fields_raw)
        weights_raw = raw.get("weights", {})
        if not isinstance(weights_raw, Mapping):
            raise ValidationError("intake pipeline weights must be an object")
        if any(isinstance(value, bool) for value in weights_raw.values()):
            raise ValidationError("intake pipeline weights must be numeric")
        try:
            weights = {str(key): float(value) for key, value in weights_raw.items()}
        except (TypeError, ValueError, OverflowError) as error:
            raise ValidationError("intake pipeline weights must be numeric") from error
        if any(not math.isfinite(value) for value in weights.values()):
            raise ValidationError("intake pipeline weights must be finite")
        source_ids_raw = raw.get("source_ids", ())
        if not isinstance(source_ids_raw, Sequence) or isinstance(source_ids_raw, (str, bytes)):
            raise ValidationError("intake pipeline source_ids must be an array")
        source_ids = tuple(source_ids_raw)
        if not source_ids:
            source_ids = tuple(
                sorted(
                    {
                        str(row.get("source_id", "")).strip()
                        for row in records
                        if str(row.get("source_id", "")).strip()
                    }
                )
            )
        minimum_score_raw = raw.get("minimum_score", 0.8)
        if isinstance(minimum_score_raw, bool):
            raise ValidationError("minimum_score must be numeric")
        try:
            minimum_score = float(minimum_score_raw)
        except (TypeError, ValueError, OverflowError) as error:
            raise ValidationError("minimum_score must be numeric") from error
        return cls(
            request_id=raw.get("request_id", "intake-pipeline-request"),
            bundle_id=raw.get("bundle_id", "intake-pipeline-bundle"),
            context_key=raw.get("context_key", ""),
            policy_id=raw.get("policy_id", ""),
            policy_version=raw.get("policy_version", ""),
            purpose=raw.get("purpose", ""),
            permitted_uses=tuple(raw.get("permitted_uses", ())),
            records=tuple(records),
            policy_source_id=raw.get("policy_source_id", ""),
            source_ids=source_ids,
            required_fields=fields,
            weights=weights,
            minimum_score=minimum_score,
            allowed_bases=raw.get("allowed_bases", "ACGTN"),
            require_accepted=raw.get("require_accepted", True),
        )

    @property
    def record_ids(self) -> tuple[str, ...]:
        return tuple(
            row.get("record_id", row.get("id", "")).strip()
            for row in self.records
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class IntakeStageReceipt:
    """Public, row-counted receipt for one pipeline stage."""

    stage_id: str
    capability_id: str
    operation: str
    state: str
    input_count: int
    accepted_count: int
    review_count: int
    issue_codes: tuple[str, ...]
    output_address: str
    detail: str

    def __post_init__(self) -> None:
        for field_name in (
            "stage_id",
            "capability_id",
            "operation",
            "state",
            "output_address",
            "detail",
        ):
            require_non_empty(str(getattr(self, field_name)), field_name)
        if self.input_count < 0 or self.accepted_count < 0 or self.review_count < 0:
            raise ValidationError("stage counts must not be negative")
        if self.accepted_count + self.review_count != self.input_count:
            raise ValidationError("stage accepted and review counts must sum to input count")
        if not self.output_address.startswith("sha256:"):
            raise ValidationError("stage output_address must be content-addressed")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class IntakePipelineReport:
    """Aggregate four-stage intake result without copying raw input records."""

    request_id: str
    bundle_id: str
    context_key: str
    state: IntakePipelineState
    stage_receipts: tuple[IntakeStageReceipt, ...]
    accepted_record_ids: tuple[str, ...]
    review_record_ids: tuple[str, ...]
    blocked_record_ids: tuple[str, ...]
    issues: tuple[str, ...]
    bundle: Mapping[str, Any] | None
    content_address: str

    def __post_init__(self) -> None:
        for field_name in ("request_id", "bundle_id", "context_key"):
            require_non_empty(getattr(self, field_name), field_name)
        if not isinstance(self.state, IntakePipelineState):
            raise ValidationError("intake pipeline report state is unsupported")
        if not isinstance(self.stage_receipts, Sequence) or isinstance(self.stage_receipts, (str, bytes)):
            raise ValidationError("stage_receipts must be an array")
        if any(not isinstance(item, IntakeStageReceipt) for item in self.stage_receipts):
            raise ValidationError("stage_receipts must contain typed receipts")
        if tuple(item.stage_id for item in self.stage_receipts) != _REPORT_STAGE_IDS:
            raise ValidationError("intake pipeline stage order does not replay")
        input_count = self.stage_receipts[0].input_count
        if any(item.input_count != input_count for item in self.stage_receipts):
            raise ValidationError("intake pipeline stage input counts do not replay")
        partitions = (
            tuple(self.accepted_record_ids),
            tuple(self.review_record_ids),
            tuple(self.blocked_record_ids),
        )
        if any(not isinstance(item, str) or not item.strip() for group in partitions for item in group):
            raise ValidationError("intake pipeline report IDs must be non-empty text")
        flattened = tuple(item for group in partitions for item in group)
        if len(set(flattened)) != len(flattened) or len(flattened) != input_count:
            raise ValidationError("intake pipeline report IDs do not form a partition")
        if not isinstance(self.issues, Sequence) or isinstance(self.issues, (str, bytes)):
            raise ValidationError("intake pipeline issues must be an array")
        if any(not isinstance(item, str) or not item.strip() for item in self.issues):
            raise ValidationError("intake pipeline issues must be non-empty text")
        if tuple(self.issues) != tuple(sorted(set(self.issues))):
            raise ValidationError("intake pipeline issues must be unique and sorted")
        if self.bundle is not None:
            if not isinstance(self.bundle, Mapping) or "records" in self.bundle:
                raise ValidationError("intake pipeline bundle must be a path-free receipt")
            if self.state is IntakePipelineState.BLOCKED:
                raise ValidationError("blocked intake pipeline reports cannot publish a bundle")
        if not isinstance(self.content_address, str) or not _ADDRESS_RE.fullmatch(self.content_address):
            raise ValidationError("intake pipeline report address is invalid")
        body = {
            "request_id": self.request_id,
            "bundle_id": self.bundle_id,
            "context_key": self.context_key,
            "state": self.state,
            "stage_receipts": self.stage_receipts,
            "accepted_record_ids": self.accepted_record_ids,
            "review_record_ids": self.review_record_ids,
            "blocked_record_ids": self.blocked_record_ids,
            "issues": self.issues,
            "bundle": self.bundle,
        }
        if content_hash(body) != self.content_address:
            raise ValidationError("intake pipeline report address does not replay")

    @property
    def accepted(self) -> bool:
        return self.state == IntakePipelineState.ACCEPTED

    @property
    def published(self) -> bool:
        return self.bundle is not None and bool(self.bundle.get("content_address"))

    def to_dict(self) -> dict[str, Any]:
        result = jsonable(self)
        result["accepted"] = self.accepted
        result["published"] = self.published
        result["stage_count"] = len(self.stage_receipts)
        result["accepted_count"] = len(self.accepted_record_ids)
        result["review_count"] = len(self.review_record_ids)
        result["blocked_count"] = len(self.blocked_record_ids)
        return result


class IntakePipeline:
    """Run C13-C16 in order and propagate the weakest row state."""

    def run(self, request: IntakePipelineRequest) -> IntakePipelineReport:
        record_ids = request.record_ids
        consent = ConsentPolicyAttacher().attach(
            request.records,
            context_key=request.context_key,
            policy_id=request.policy_id,
            policy_version=request.policy_version,
            purpose=request.purpose,
            permitted_uses=request.permitted_uses,
            source_id=request.policy_source_id,
        )
        anomaly = InputAnomalyQuarantine().inspect(
            request.records,
            context_key=request.context_key,
            source_id=request.policy_source_id,
            allowed_bases=request.allowed_bases,
        )
        completeness = DataCompletenessScorer().score(
            request.records,
            context_key=request.context_key,
            required_fields=request.required_fields,
            weights=request.weights,
            minimum_score=request.minimum_score,
            source_id=request.policy_source_id,
        )
        consent_accepted = set(consent.accepted_record_ids)
        anomaly_accepted = set(anomaly.accepted_record_ids)
        completeness_accepted = set(completeness.accepted_record_ids)
        accepted = tuple(
            record_id
            for record_id in record_ids
            if record_id in consent_accepted
            and record_id in anomaly_accepted
            and record_id in completeness_accepted
        )
        accepted_set = set(accepted)
        blocked = tuple(
            record_id
            for record_id in record_ids
            if record_id not in consent_accepted or record_id not in anomaly_accepted
        )
        blocked_set = set(blocked)
        review = tuple(
            record_id for record_id in record_ids if record_id not in accepted_set and record_id not in blocked_set
        )
        stage_receipts = (
            self._consent_receipt(consent, record_ids),
            self._anomaly_receipt(anomaly, record_ids),
            self._completeness_receipt(completeness, record_ids),
        )
        issues = sorted(
            set(
                self._issue_codes(consent.to_dict())
                + self._issue_codes(anomaly.to_dict())
                + self._issue_codes(completeness.to_dict())
            )
        )
        bundle: IntakeBundle | None = None
        export_issue_codes: tuple[str, ...] = ()
        if accepted:
            accepted_rows = tuple(
                dict(row) | {"state": "accepted"}
                for row in request.records
                if str(row.get("record_id", row.get("id", ""))) in accepted_set
            )
            try:
                bundle = IntakeBundleExporter().export(
                    accepted_rows,
                    bundle_id=request.bundle_id,
                    context_key=request.context_key,
                    source_ids=request.source_ids,
                    require_accepted=request.require_accepted,
                )
            except ValidationError:
                export_issue_codes = ("validation_error",)
        export_count = len(bundle.records) if bundle is not None else 0
        export_state = "published" if bundle is not None else "blocked"
        export_receipt = IntakeStageReceipt(
            "export",
            "GNC-D01-C16",
            "export-intake-bundle",
            export_state,
            len(record_ids),
            export_count,
            len(record_ids) - export_count,
            tuple(sorted(set(export_issue_codes))),
            bundle.content_address if bundle is not None else content_hash(
                {"bundle_id": request.bundle_id, "state": export_state, "issues": export_issue_codes}
            ),
            "accepted intersection is exported only after the preceding three gates",
        )
        stage_receipts = stage_receipts + (export_receipt,)
        issues = sorted(set(issues) | set(export_issue_codes))
        if not accepted:
            state = IntakePipelineState.BLOCKED
        elif bundle is None:
            state = IntakePipelineState.REVIEW
        elif len(accepted) != len(record_ids):
            state = IntakePipelineState.REVIEW
        else:
            state = IntakePipelineState.ACCEPTED
        bundle_receipt = self._bundle_receipt(bundle)
        body = {
            "request_id": request.request_id,
            "bundle_id": request.bundle_id,
            "context_key": request.context_key,
            "state": state,
            "stage_receipts": stage_receipts,
            "accepted_record_ids": accepted,
            "review_record_ids": review,
            "blocked_record_ids": blocked,
            "issues": issues,
            "bundle": bundle_receipt,
        }
        return IntakePipelineReport(
            request.request_id,
            request.bundle_id,
            request.context_key,
            state,
            stage_receipts,
            accepted,
            review,
            blocked,
            tuple(issues),
            bundle_receipt,
            content_hash(body),
        )

    @staticmethod
    def _consent_receipt(report: Any, record_ids: tuple[str, ...]) -> IntakeStageReceipt:
        accepted = tuple(report.accepted_record_ids)
        return IntakeStageReceipt(
            "consent",
            "GNC-D01-C13",
            "attach-consent-policy",
            "accepted" if len(accepted) == len(record_ids) else "review",
            len(record_ids),
            len(accepted),
            len(record_ids) - len(accepted),
            IntakePipeline._issue_codes(report.to_dict()),
            report.content_address,
            "policy status and exact context are checked before downstream export",
        )

    @staticmethod
    def _anomaly_receipt(report: Any, record_ids: tuple[str, ...]) -> IntakeStageReceipt:
        accepted = tuple(report.accepted_record_ids)
        return IntakeStageReceipt(
            "anomaly",
            "GNC-D01-C14",
            "quarantine-input-anomalies",
            "accepted" if len(accepted) == len(record_ids) else "review",
            len(record_ids),
            len(accepted),
            len(record_ids) - len(accepted),
            IntakePipeline._issue_codes(report.to_dict()),
            report.content_address,
            "malformed rows remain addressable and are removed from the accepted intersection",
        )

    @staticmethod
    def _completeness_receipt(report: Any, record_ids: tuple[str, ...]) -> IntakeStageReceipt:
        accepted = tuple(report.accepted_record_ids)
        return IntakeStageReceipt(
            "completeness",
            "GNC-D01-C15",
            "score-data-completeness",
            "accepted" if len(accepted) == len(record_ids) else "review",
            len(record_ids),
            len(accepted),
            len(record_ids) - len(accepted),
            IntakePipeline._issue_codes(report.to_dict()),
            report.content_address,
            "weighted field coverage is required before a row enters the export intersection",
        )

    @staticmethod
    def _issue_codes(value: Any) -> tuple[str, ...]:
        codes: list[str] = []
        if isinstance(value, Mapping):
            for key, child in value.items():
                if key in {"code", "error_code"} and isinstance(child, str):
                    codes.append(child)
                else:
                    codes.extend(IntakePipeline._issue_codes(child))
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            for child in value:
                codes.extend(IntakePipeline._issue_codes(child))
        return tuple(sorted(set(codes)))

    @staticmethod
    def _bundle_receipt(bundle: IntakeBundle | None) -> dict[str, Any] | None:
        """Return manifest metadata without copying accepted raw rows."""

        if bundle is None:
            return None
        payload = bundle.to_dict()
        payload.pop("records", None)
        return payload


def run_intake_pipeline(raw: Mapping[str, Any]) -> IntakePipelineReport:
    """Parse and execute a C13-C16 intake pipeline request."""

    return IntakePipeline().run(IntakePipelineRequest.from_mapping(raw))


__all__ = [
    "IntakePipeline",
    "IntakePipelineReport",
    "IntakePipelineRequest",
    "IntakePipelineState",
    "IntakeStageReceipt",
    "run_intake_pipeline",
]
