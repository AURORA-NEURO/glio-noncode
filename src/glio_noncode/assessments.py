"""Replay-closed run assessments spanning quality, projection, and rendered bytes."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .errors import ValidationError
from .quality import QualityEvaluator, QualityReport, QualityThresholds
from .reports import (
    DossierReport,
    RenderedReport,
    ReportAudience,
    ReportFormat,
    build_report,
    render_report,
)
from .serialization import canonical_bytes, content_hash

if TYPE_CHECKING:
    from .runtime import VerifiedRunSnapshot


RUN_ASSESSMENT_VERSION = "run-assessment-v1"
_HARD_MAX_RUN_ASSESSMENT_BYTES = 40 * 1024 * 1024
MAX_RUN_ASSESSMENT_BYTES = _HARD_MAX_RUN_ASSESSMENT_BYTES
_RUN_ASSESSMENT_FIELDS = frozenset(
    {
        "assessment_version",
        "run_id",
        "input_address",
        "event_address",
        "dossier_address",
        "quality_report",
        "dossier_report",
        "rendered_report",
        "content_address",
    }
)


def _address(value: object, field_name: str, *, prefix: str) -> str:
    if type(value) is not str or not value.startswith(f"{prefix}:"):
        raise ValidationError(f"{field_name} must use the {prefix} content-address namespace")
    digest = value.split(":", 1)[1]
    if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
        raise ValidationError(f"{field_name} must be a canonical content address")
    return value


def _assessment_body(value: VerifiedRunAssessment) -> dict[str, object]:
    return {
        "assessment_version": value.assessment_version,
        "run_id": value.run_id,
        "input_address": value.input_address,
        "event_address": value.event_address,
        "dossier_address": value.dossier_address,
        "quality_report": value.quality_report.to_dict(),
        "dossier_report": value.dossier_report.to_dict(),
        "rendered_report": value.rendered_report.to_dict(),
    }


@dataclass(frozen=True, slots=True)
class VerifiedRunAssessment:
    """One addressed closure over a verified run and every report-stage artifact."""

    assessment_version: str
    run_id: str
    input_address: str
    event_address: str
    dossier_address: str
    quality_report: QualityReport
    dossier_report: DossierReport
    rendered_report: RenderedReport
    content_address: str = ""

    def __post_init__(self, _hard_max_bytes: int = _HARD_MAX_RUN_ASSESSMENT_BYTES) -> None:
        if self.assessment_version != RUN_ASSESSMENT_VERSION:
            raise ValidationError("run assessment version is unsupported")
        if (
            type(self.run_id) is not str
            or not self.run_id.startswith("run-")
            or len(self.run_id) > 128
        ):
            raise ValidationError("run assessment run_id is invalid")
        _address(self.input_address, "run assessment input_address", prefix="sha256")
        _address(self.event_address, "run assessment event_address", prefix="sha256")
        _address(self.dossier_address, "run assessment dossier_address", prefix="sha256")
        if type(self.quality_report) is not QualityReport:
            raise ValidationError("run assessment quality_report must be exact")
        if type(self.dossier_report) is not DossierReport:
            raise ValidationError("run assessment dossier_report must be exact")
        if type(self.rendered_report) is not RenderedReport:
            raise ValidationError("run assessment rendered_report must be exact")
        self.quality_report.to_dict()
        self.dossier_report.to_dict()
        self.rendered_report.to_dict()
        if (
            self.quality_report.dossier_address != self.dossier_address
            or self.dossier_report.dossier_address != self.dossier_address
            or self.rendered_report.dossier_address != self.dossier_address
            or not self.rendered_report.verify(self.dossier_report)
        ):
            raise ValidationError("run assessment report artifacts do not share one dossier")
        expected = content_hash(_assessment_body(self), prefix="run-assessment")
        if self.content_address:
            supplied = _address(
                self.content_address,
                "run assessment content_address",
                prefix="run-assessment",
            )
            if supplied != expected:
                raise ValidationError("run assessment content_address does not match its payload")
        object.__setattr__(self, "content_address", expected)
        if len(canonical_bytes(self.to_dict())) > _hard_max_bytes:
            raise ValidationError("run assessment exceeds its serialized-size ceiling")

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> VerifiedRunAssessment:
        if type(raw) is not dict or set(raw) != _RUN_ASSESSMENT_FIELDS:
            raise ValidationError("run assessment fields must be exact")
        quality_raw = raw["quality_report"]
        report_raw = raw["dossier_report"]
        rendered_raw = raw["rendered_report"]
        if (
            type(quality_raw) is not dict
            or type(report_raw) is not dict
            or type(rendered_raw) is not dict
        ):
            raise ValidationError("run assessment nested reports must be exact objects")
        value = cls(
            assessment_version=raw["assessment_version"],
            run_id=raw["run_id"],
            input_address=raw["input_address"],
            event_address=raw["event_address"],
            dossier_address=raw["dossier_address"],
            quality_report=QualityReport.from_dict(quality_raw),
            dossier_report=DossierReport.from_dict(report_raw),
            rendered_report=RenderedReport.from_dict(rendered_raw),
            content_address=raw["content_address"],
        )
        if canonical_bytes(raw) != canonical_bytes(value.to_dict()):
            raise ValidationError("run assessment is not an exact canonical representation")
        return value

    def verify(self, snapshot: VerifiedRunSnapshot) -> bool:
        """Recompute every derived artifact against one replay-verified snapshot."""

        try:
            expected = build_run_assessment(
                snapshot,
                audience=self.dossier_report.audience,
                format=self.rendered_report.format,
                quality_thresholds=self.quality_report.thresholds,
            )
            return canonical_bytes(self.to_dict()) == canonical_bytes(expected.to_dict())
        except Exception:  # noqa: BLE001 - verification intentionally fails closed
            return False

    def verify_without_rebuild(self, snapshot: VerifiedRunSnapshot) -> bool:
        """Verify direct provenance and each report against an already verified snapshot."""

        try:
            from .runtime import VerifiedRunSnapshot

            if type(snapshot) is not VerifiedRunSnapshot:
                return False
            record = snapshot.run_record
            return (
                self.run_id == snapshot.dossier.run_id
                and self.input_address == record["input_address"]
                and self.event_address == record["event_address"]
                and self.dossier_address == snapshot.dossier.content_address
                and self.quality_report.verify(snapshot.dossier)
                and self.dossier_report.verify(snapshot.dossier)
                and self.rendered_report.verify(self.dossier_report)
            )
        except Exception:  # noqa: BLE001 - verification intentionally fails closed
            return False

    def to_dict(
        self,
        _hard_max_bytes: int = _HARD_MAX_RUN_ASSESSMENT_BYTES,
    ) -> dict[str, object]:
        if (
            type(self.quality_report) is not QualityReport
            or type(self.dossier_report) is not DossierReport
            or type(self.rendered_report) is not RenderedReport
        ):
            raise ValidationError("run assessment nested reports must remain exact")
        body = _assessment_body(self)
        expected = content_hash(body, prefix="run-assessment")
        supplied = _address(
            self.content_address,
            "run assessment content_address",
            prefix="run-assessment",
        )
        if supplied != expected:
            raise ValidationError("run assessment content_address does not match its payload")
        payload = body | {"content_address": supplied}
        if len(canonical_bytes(payload)) > _hard_max_bytes:
            raise ValidationError("run assessment exceeds its serialized-size ceiling")
        return payload


def build_run_assessment(
    snapshot: VerifiedRunSnapshot,
    *,
    audience: ReportAudience | str = ReportAudience.PUBLIC,
    format: ReportFormat | str = ReportFormat.JSON,
    quality_thresholds: QualityThresholds | None = None,
) -> VerifiedRunAssessment:
    """Derive one quality-and-rendering closure from a single verified run read."""

    from .runtime import VerifiedRunSnapshot

    if type(snapshot) is not VerifiedRunSnapshot:
        raise ValidationError("run assessment requires an exact VerifiedRunSnapshot")
    quality = QualityEvaluator(thresholds=quality_thresholds).evaluate(snapshot.dossier)
    report = build_report(snapshot.dossier, audience=audience)
    rendered = render_report(report, format=format)
    run_record = snapshot.run_record
    value = VerifiedRunAssessment(
        assessment_version=RUN_ASSESSMENT_VERSION,
        run_id=snapshot.dossier.run_id,
        input_address=run_record["input_address"],
        event_address=run_record["event_address"],
        dossier_address=snapshot.dossier.content_address,
        quality_report=quality,
        dossier_report=report,
        rendered_report=rendered,
    )
    if not value.verify_without_rebuild(snapshot):  # pragma: no cover - construction invariant
        raise ValidationError("constructed run assessment does not close over its snapshot")
    return value


def assessment_capabilities() -> dict[str, object]:
    """Return deterministic discovery metadata for the run-assessment boundary."""

    return {
        "assessment_version": RUN_ASSESSMENT_VERSION,
        "default_audience": ReportAudience.PUBLIC.value,
        "default_format": ReportFormat.JSON.value,
        "audiences": [item.value for item in ReportAudience],
        "formats": [item.value for item in ReportFormat],
        "features": [
            "single verified run read",
            "recomputed quality report",
            "audience-scoped dossier projection",
            "byte-addressed rendering",
            "cross-artifact provenance verification",
        ],
        "hard_limits": {"assessment_bytes": _HARD_MAX_RUN_ASSESSMENT_BYTES},
    }


__all__ = [
    "MAX_RUN_ASSESSMENT_BYTES",
    "RUN_ASSESSMENT_VERSION",
    "VerifiedRunAssessment",
    "assessment_capabilities",
    "build_run_assessment",
]
