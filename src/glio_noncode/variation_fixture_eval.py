"""Executable public-aggregate evidence for Domain 01 variation operations.

The evaluator is deliberately independent of the individual operation tests.
It runs one fixture through the VRS-shaped normalizer, categorical matcher,
annotation envelope builder, multi-allelic decomposer, and repeat-aware
normalizer. Positive records and review controls share the same adapter path,
which prevents the fixture from proving only happy-path serialization.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty
from .variant_beta import (
    CategoricalCatalogParser,
    CatVRSNormalizer,
    MultiAllelicDecomposer,
    RepeatAwareNormalizer,
    VAAnnotationEnvelopeBuilder,
)
from .variant_normalization import VRSNormalizer
from .variation_public_data import (
    VARIATION_FIXTURE_SCHEMA_VERSION,
    VariationDataState,
    VariationFixtureCatalog,
    VariationFixtureRecord,
    VariationRecordKind,
)


@dataclass(frozen=True, slots=True)
class VariationFixtureCheck:
    """One expected state or invariant assertion from the variation fixture."""

    check_id: str
    expected: Any
    observed: Any
    passed: bool
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.check_id, "check_id")
        require_non_empty(self.detail, "detail")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class VariationFixtureEvaluationReport:
    """Complete operation and review-boundary result for one fixture."""

    fixture_id: str
    fixture_version: str
    context_key: str
    source_ids: tuple[str, ...]
    data_report: Mapping[str, Any]
    positive_reports: Mapping[str, Mapping[str, Any]]
    negative_reports: Mapping[str, Mapping[str, Any]]
    checks: tuple[VariationFixtureCheck, ...]
    passed_check_ids: tuple[str, ...]
    failed_check_ids: tuple[str, ...]
    evidence_boundary: str
    state: VariationDataState
    content_address: str

    @property
    def passed(self) -> bool:
        return self.state == VariationDataState.ACCEPTED and not self.failed_check_ids

    def to_dict(self) -> dict[str, Any]:
        result = jsonable(self)
        result["passed"] = self.passed
        result["check_count"] = len(self.checks)
        result["passed_count"] = len(self.passed_check_ids)
        result["failed_count"] = len(self.failed_check_ids)
        return result


class VariationFixtureEvaluator:
    """Run the checked-in public aggregate fixture through five D01 adapters."""

    _expected_kinds = {
        VariationRecordKind.VRS,
        VariationRecordKind.CATEGORICAL,
        VariationRecordKind.ANNOTATION,
        VariationRecordKind.MULTIALLELIC,
        VariationRecordKind.REPEAT,
    }

    def load_file(self, path: str | Path) -> Mapping[str, Any]:
        fixture_path = Path(path)
        try:
            raw = json.loads(fixture_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValidationError(f"variation fixture is not valid JSON: {fixture_path}") from exc
        if not isinstance(raw, Mapping):
            raise ValidationError("variation fixture must be an object")
        self.validate_fixture(raw)
        return raw

    def validate_fixture(self, raw: Mapping[str, Any]) -> VariationFixtureCatalog:
        catalog = VariationFixtureCatalog.from_fixture(raw)
        if catalog.fixture_version != VARIATION_FIXTURE_SCHEMA_VERSION:
            raise ValidationError(
                f"fixture_version must be {VARIATION_FIXTURE_SCHEMA_VERSION}, "
                f"received {catalog.fixture_version}"
            )
        if not catalog.records:
            raise ValidationError("variation fixture must declare positive records")
        observed_kinds = {record.kind for record in catalog.records}
        missing_kinds = self._expected_kinds - observed_kinds
        if missing_kinds:
            raise ValidationError(
                "variation fixture is missing record kinds: "
                + ", ".join(sorted(kind.value for kind in missing_kinds))
            )
        controls = raw.get("negative_controls")
        if not isinstance(controls, Sequence) or isinstance(controls, (str, bytes)):
            raise ValidationError("variation negative_controls must be an array")
        if not controls:
            raise ValidationError("variation fixture must declare negative controls")
        return catalog

    def evaluate_file(self, path: str | Path) -> VariationFixtureEvaluationReport:
        raw = self.load_file(path)
        return self.evaluate(raw)

    def evaluate(self, raw: Mapping[str, Any]) -> VariationFixtureEvaluationReport:
        catalog = self.validate_fixture(raw)
        data_report = catalog.audit()
        context = _context_mapping(raw.get("context"))
        context_key = catalog.context_key
        checks: list[VariationFixtureCheck] = []
        positive_reports: dict[str, Mapping[str, Any]] = {}
        negative_reports: dict[str, Mapping[str, Any]] = {}
        self._append_check(
            checks,
            "data-boundary:variation-catalog",
            True,
            data_report.accepted,
            "public aggregate records have source receipts, exact context, and no sensitive paths",
            data_report.to_dict(),
        )
        for record in catalog.records:
            output = self._run_record(record, context, context_key)
            serialized = _serialize_output(output)
            positive_reports[record.record_id] = serialized
            observed = _state_value(output)
            self._append_check(
                checks,
                f"positive:{record.record_id}",
                record.expected_state,
                observed,
                f"{record.kind.value} operation returned the declared public-fixture state",
                serialized,
            )
            self._append_check(
                checks,
                f"trace:{record.record_id}",
                True,
                record.public_identifier in json.dumps(serialized, sort_keys=True),
                "public aggregate identity remains traceable in the operation receipt",
                serialized,
            )
            self._append_check(
                checks,
                f"address:{record.record_id}",
                True,
                _has_address(serialized),
                "operation output is content-addressed",
                serialized,
            )
        controls = raw.get("negative_controls", ())
        for index, control in enumerate(controls):
            if not isinstance(control, Mapping):
                raise ValidationError(f"negative_controls[{index}] must be an object")
            control_id = require_non_empty(str(control.get("control_id", "")), "control_id")
            kind = VariationRecordKind(str(control.get("kind", "")))
            payload = control.get("payload")
            if not isinstance(payload, Mapping):
                raise ValidationError(f"negative control {control_id} payload must be an object")
            expected_state = require_non_empty(
                str(control.get("expected_state", "")), f"{control_id}.expected_state"
            )
            record = VariationFixtureRecord(
                record_id=f"negative:{control_id}",
                kind=kind,
                operation=str(control.get("operation", kind.value)),
                source_id=str(control.get("source_id", "fixture-negative")),
                context_key=str(control.get("context_key", context_key)),
                payload=payload,
                public_identifier=str(control.get("public_identifier", control_id)),
                expected_state=expected_state,
            )
            output = self._run_record(record, context, context_key)
            serialized = _serialize_output(output)
            negative_reports[control_id] = serialized
            observed = _state_value(output)
            self._append_check(
                checks,
                f"negative:{control_id}",
                expected_state,
                observed,
                "negative control retains its declared abstention or out-of-domain state",
                serialized,
            )
            required_issue_codes = tuple(
                str(item) for item in control.get("required_issue_codes", ())
            )
            issue_codes = _issue_codes(serialized)
            self._append_check(
                checks,
                f"negative-issues:{control_id}",
                True,
                all(code in issue_codes for code in required_issue_codes),
                "negative control exposes the required structured reason codes",
                {"issue_codes": issue_codes, "result": serialized},
            )
        expected_negative_count = int(raw.get("expected_negative_control_count", len(controls)))
        self._append_check(
            checks,
            "negative-control-floor",
            expected_negative_count,
            len(negative_reports),
            "all declared variation review controls were executed",
            negative_reports,
        )
        repeated = self._run_record(catalog.records[0], context, context_key)
        first_address = _content_address(positive_reports[catalog.records[0].record_id])
        second_address = _content_address(_serialize_output(repeated))
        self._append_check(
            checks,
            "deterministic:variation-first-record",
            True,
            first_address == second_address,
            "repeated evaluation produces one operation content address",
            {"first": first_address, "second": second_address},
        )
        serialized_all = json.dumps(
            {"positive": positive_reports, "negative": negative_reports}, sort_keys=True
        ).casefold()
        self._append_check(
            checks,
            "output-boundary:variation",
            False,
            any(
                fragment in serialized_all
                for fragment in ("patient_id", "medical_record", "mrn", "password", "secret")
            ),
            "operation receipts do not expose restricted fixture fields",
            {"restricted_output": serialized_all},
        )
        passed_ids = tuple(check.check_id for check in checks if check.passed)
        failed_ids = tuple(check.check_id for check in checks if not check.passed)
        state = VariationDataState.ACCEPTED if not failed_ids else VariationDataState.REVIEW
        boundary = require_non_empty(
            str(catalog.provenance.get("evidence_boundary", "")),
            "provenance.evidence_boundary",
        )
        body = {
            "fixture_id": catalog.fixture_id,
            "fixture_version": catalog.fixture_version,
            "context_key": context_key,
            "source_ids": tuple(sorted(source.source_id for source in catalog.sources)),
            "data_report": data_report,
            "positive_reports": positive_reports,
            "negative_reports": negative_reports,
            "checks": checks,
        }
        return VariationFixtureEvaluationReport(
            catalog.fixture_id,
            catalog.fixture_version,
            context_key,
            tuple(sorted(source.source_id for source in catalog.sources)),
            data_report.to_dict(),
            positive_reports,
            negative_reports,
            tuple(checks),
            passed_ids,
            failed_ids,
            boundary,
            state,
            content_hash(body),
        )

    def run_record(
        self,
        record: VariationFixtureRecord,
        context: Mapping[str, str],
        context_key: str,
    ) -> Any:
        """Run one validated record for independent scenario inspection."""

        return self._run_record(record, context, context_key)

    @staticmethod
    def _append_check(
        checks: list[VariationFixtureCheck],
        check_id: str,
        expected: Any,
        observed: Any,
        detail: str,
        receipt: Any,
    ) -> None:
        if isinstance(expected, bool):
            passed = bool(observed) == expected
        else:
            passed = observed == expected
        checks.append(
            VariationFixtureCheck(
                check_id,
                expected,
                observed,
                passed,
                detail,
                content_hash(receipt),
            )
        )

    @staticmethod
    def _run_record(
        record: VariationFixtureRecord,
        context: Mapping[str, str],
        context_key: str,
    ) -> Any:
        payload = dict(record.payload)
        genome_build = context["genome_build"]
        if record.kind == VariationRecordKind.VRS:
            return VRSNormalizer().normalize(
                payload,
                genome_build=genome_build,
                sequence_digest=payload.get("sequence_digest"),
                reference_sequence=payload.get("reference_sequence"),
                reference_start=payload.get("reference_start"),
            )
        if record.kind == VariationRecordKind.CATEGORICAL:
            definitions = payload.get("catalog", ())
            if not isinstance(definitions, Sequence) or isinstance(definitions, (str, bytes)):
                raise ValidationError(f"{record.record_id} categorical catalog must be an array")
            catalog_text = json.dumps(definitions, sort_keys=True)
            batch = CategoricalCatalogParser().parse_json(
                catalog_text,
                source_id=record.source_id,
                source_version=str(payload.get("source_version", "fixture")),
            )
            query = payload.get("query", payload.get("input", {}))
            return CatVRSNormalizer(batch.definitions).normalize(query)
        if record.kind == VariationRecordKind.ANNOTATION:
            return VAAnnotationEnvelopeBuilder().build_from_mappings(
                str(payload.get("annotation_id", record.record_id)),
                payload.get("subject", {}),
                payload.get("statements", ()),
                payload.get("evidence_lines", payload.get("evidence", ())),
                context_key=context_key,
            )
        if record.kind == VariationRecordKind.MULTIALLELIC:
            return MultiAllelicDecomposer().decompose(
                payload,
                genome_build=genome_build,
                source_id=record.source_id,
                source_version=str(payload.get("source_version", "fixture")),
            )
        if record.kind == VariationRecordKind.REPEAT:
            return RepeatAwareNormalizer().normalize(
                payload.get("variant", payload),
                reference_sequence=str(payload.get("reference_sequence", "")),
                reference_start=int(payload.get("reference_start", 0)),
                max_shift_bp=int(payload.get("max_shift_bp", 50)),
                genome_build=genome_build,
            )
        raise ValidationError(f"unsupported variation record kind: {record.kind}")


def _context_mapping(value: Any) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise ValidationError("variation context must be an object")
    fields = (
        "genome_build",
        "disease_class",
        "age_group",
        "cell_state",
        "territory",
        "treatment_phase",
    )
    return {
        field: require_non_empty(str(value.get(field, "")), f"context.{field}")
        for field in fields
    }


def _state_value(value: Any) -> str:
    state = getattr(value, "state", "invalid")
    return str(getattr(state, "value", state))


def _serialize_output(value: Any) -> dict[str, Any]:
    if not hasattr(value, "to_dict"):
        raise ValidationError("variation operation did not return a serializable report")
    result = value.to_dict()
    if not isinstance(result, Mapping):
        raise ValidationError("variation operation report must serialize to an object")
    return dict(result)


def _has_address(value: Any) -> bool:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if key in {"content_address", "input_hash", "raw_hash"} and isinstance(child, str):
                if key == "content_address" and child.startswith("sha256:"):
                    return True
            if _has_address(child):
                return True
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return any(_has_address(child) for child in value)
    return False


def _content_address(value: Mapping[str, Any]) -> str | None:
    address = value.get("content_address")
    return address if isinstance(address, str) else None


def _issue_codes(value: Any) -> tuple[str, ...]:
    codes: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            if key == "code" and isinstance(child, str):
                codes.append(child)
            else:
                codes.extend(_issue_codes(child))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for child in value:
            codes.extend(_issue_codes(child))
    return tuple(sorted(set(codes)))


def evaluate_variation_fixture(path: str | Path) -> VariationFixtureEvaluationReport:
    """Convenience function for one public aggregate variation fixture."""

    return VariationFixtureEvaluator().evaluate_file(path)


__all__ = [
    "VariationFixtureCheck",
    "VariationFixtureEvaluationReport",
    "VariationFixtureEvaluator",
    "evaluate_variation_fixture",
]
