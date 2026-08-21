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
            require_non_empty(str(getattr(self, field_name)), field_name)
        if not self.permitted_uses:
            raise ValidationError("permitted_uses must not be empty")
        if not self.records:
            raise ValidationError("records must not be empty")
        if not self.source_ids:
            raise ValidationError("source_ids must not be empty")
        if not self.required_fields:
            raise ValidationError("required_fields must not be empty")
        if len(self.required_fields) != len(set(self.required_fields)):
            raise ValidationError("required_fields must be unique")
        if self.minimum_score < 0.0 or self.minimum_score > 1.0:
            raise ValidationError("minimum_score must be between 0 and 1")
        record_ids: list[str] = []
        for index, row in enumerate(self.records, start=1):
            if not isinstance(row, Mapping):
                raise ValidationError(f"records[{index - 1}] must be an object")
            record_id = str(row.get("record_id", row.get("id", ""))).strip()
            if not record_id:
                raise ValidationError(f"records[{index - 1}] requires record_id")
            record_ids.append(record_id)
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
        records_raw = raw.get("records", ())
        if not isinstance(records_raw, Sequence) or isinstance(records_raw, (str, bytes)):
            raise ValidationError("intake pipeline records must be an array")
        records: list[Mapping[str, Any]] = []
        for index, row in enumerate(records_raw):
            if not isinstance(row, Mapping):
                raise ValidationError(f"intake pipeline records[{index}] must be an object")
            records.append(dict(row))
        fields = tuple(str(item) for item in raw.get("required_fields", ()))
        weights_raw = raw.get("weights", {})
        if not isinstance(weights_raw, Mapping):
            raise ValidationError("intake pipeline weights must be an object")
        weights = {str(key): float(value) for key, value in weights_raw.items()}
        source_ids = tuple(str(item) for item in raw.get("source_ids", ()))
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
        return cls(
            request_id=str(raw.get("request_id", "intake-pipeline-request")),
            bundle_id=str(raw.get("bundle_id", "intake-pipeline-bundle")),
            context_key=str(raw.get("context_key", "")),
            policy_id=str(raw.get("policy_id", "")),
            policy_version=str(raw.get("policy_version", "")),
            purpose=str(raw.get("purpose", "")),
            permitted_uses=tuple(str(item) for item in raw.get("permitted_uses", ())),
            records=tuple(records),
            policy_source_id=str(raw.get("policy_source_id", "")),
            source_ids=source_ids,
            required_fields=fields,
            weights=weights,
            minimum_score=float(raw.get("minimum_score", 0.8)),
            allowed_bases=str(raw.get("allowed_bases", "ACGTN")),
            require_accepted=bool(raw.get("require_accepted", True)),
        )

    @property
    def record_ids(self) -> tuple[str, ...]:
        return tuple(str(row.get("record_id", row.get("id", ""))) for row in self.records)

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
