"""Repository-level evaluation for the D13-D16 frontier controls.

The evaluator treats a fixture as a small, declared research dataset rather
than as a collection of ad-hoc test arguments.  It validates provenance,
normalizes the exact glioma context, executes the four frontier pipelines,
executes the hardening operations, and then checks negative controls.  Every
check retains the observed state and content address so a failed quality gate
can be inspected without rerunning hidden steps.

The fixture boundary is deliberately narrow.  It proves deterministic input
validation, state transitions, receipts, and failure handling.  It does not
prove biological effect, clinical utility, or transport to an external cohort.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .frontier_contracts import default_frontier_contract_registry
from .frontier_data_alpha import FrontierState
from .frontier_end_to_end import (
    DeploymentGovernancePipeline,
    EvidenceLifecyclePipeline,
    FrontierPipelineReport,
    ValidationFrontierPipeline,
    WorkbenchQualityPipeline,
    run_end_to_end_operation,
)
from .frontier_public_data import PublicFixtureCatalog
from .frontier_release_alpha import (
    RELEASE_FRONTIER_OPERATIONS,
    run_release_frontier_operation,
)
from .frontier_release_hardening import (
    HARDENING_OPERATIONS,
    run_hardening_operation,
)
from .serialization import content_hash, jsonable, require_non_empty

FIXTURE_SCHEMA_VERSION = "frontier-fixture-v1"
_CONTEXT_FIELDS = (
    "genome_build",
    "disease_class",
    "age_group",
    "cell_state",
    "territory",
    "treatment_phase",
)
_ACCEPTED = FrontierState.ACCEPTED.value
_SUCCESS_STATES = frozenset(
    {
        FrontierState.ACCEPTED.value,
        FrontierState.PUBLISHED.value,
        "ready",
        "released",
        "rolled_back",
    }
)


def _mapping(value: Any, *, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{label} must be an object")
    return value


def _sequence(value: Any, *, label: str) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValidationError(f"{label} must be an array")
    return tuple(value)


def _text(value: Any, *, field: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValidationError(f"{field} must be text")
    return value.strip()


def _required_text(value: Any, *, field: str) -> str:
    return require_non_empty(_text(value, field=field), field)


def _state(value: Any) -> str:
    if isinstance(value, FrontierState):
        return value.value
    return str(value)


def _context_key(context: Mapping[str, Any]) -> str:
    values = tuple(
        _required_text(context.get(field), field=f"context.{field}") for field in _CONTEXT_FIELDS
    )
    return "|".join(values)


def _content_address(value: Any) -> str:
    return content_hash(jsonable(value))


@dataclass(frozen=True, slots=True)
class FixtureCheck:
    """One deterministic fixture expectation and its observed receipt."""

    check_id: str
    capability_ids: tuple[str, ...]
    expected_state: str
    observed_state: str
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FixtureEvaluationReport:
    """Complete output of a frontier fixture run."""

    fixture_id: str
    fixture_version: str
    context_key: str
    source_ids: tuple[str, ...]
    contract_manifest: Mapping[str, Any]
    data_report: Mapping[str, Any]
    pipeline_reports: Mapping[str, Mapping[str, Any]]
    operation_reports: Mapping[str, Mapping[str, Any]]
    hardening_reports: Mapping[str, Mapping[str, Any]]
    negative_control_reports: Mapping[str, Mapping[str, Any]]
    checks: tuple[FixtureCheck, ...]
    passed_check_ids: tuple[str, ...]
    failed_check_ids: tuple[str, ...]
    state: FrontierState
    evidence_boundary: str
    content_address: str

    @property
    def passed(self) -> bool:
        return not self.failed_check_ids and self.state == FrontierState.ACCEPTED

    def to_dict(self) -> dict[str, Any]:
        result = jsonable(self)
        result["passed"] = self.passed
        result["check_count"] = len(self.checks)
        result["passed_count"] = len(self.passed_check_ids)
        result["failed_count"] = len(self.failed_check_ids)
        return result


class FrontierFixtureEvaluator:
    """Run a declared fixture against every D13-D16 frontier control."""

    _pipeline_capabilities = {
        "validation": (
            ("off_target_risk", "GNC-D13-C13"),
            ("value_of_information", "GNC-D13-C14"),
            ("experiment_package", "GNC-D13-C15"),
            ("claim_update", "GNC-D13-C16"),
        ),
        "evidence": (
            ("reclassification", "GNC-D14-C13"),
            ("supersession", "GNC-D14-C14"),
            ("audit_bundle", "GNC-D14-C15"),
            ("signed_dossier", "GNC-D14-C16"),
        ),
        "workbench": (
            ("structured_review", "GNC-D15-C13"),
            ("report_export", "GNC-D15-C14"),
            ("search_palette", "GNC-D15-C15"),
            ("accessibility", "GNC-D15-C16"),
        ),
        "deployment": (
            ("security_policy", "GNC-D16-C13"),
            ("deployment_bundle", "GNC-D16-C14"),
            ("federated_execution", "GNC-D16-C15"),
            ("release_rollback", "GNC-D16-C16"),
        ),
    }

    def load_file(self, path: str | Path) -> Mapping[str, Any]:
        """Read one UTF-8 JSON fixture and validate its top-level shape."""

        fixture_path = Path(path)
        try:
            raw = json.loads(fixture_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValidationError(f"fixture is not valid JSON: {fixture_path}") from exc
        return self.validate_fixture(raw)

    def validate_fixture(self, raw: Mapping[str, Any]) -> Mapping[str, Any]:
        """Validate the fixture contract without executing any capability."""

        data = _mapping(raw, label="frontier fixture")
        version = _required_text(data.get("fixture_version"), field="fixture_version")
        if version != FIXTURE_SCHEMA_VERSION:
            raise ValidationError(
                f"fixture_version must be {FIXTURE_SCHEMA_VERSION}, received {version}"
            )
        _required_text(data.get("fixture_id"), field="fixture_id")
        provenance = _mapping(data.get("provenance"), label="provenance")
        for field in ("source_class", "license", "patient_level_data", "numeric_values"):
            if field not in provenance:
                raise ValidationError(f"provenance.{field} is required")
        if provenance["patient_level_data"] is not False:
            raise ValidationError("frontier fixture must not contain patient-level data")
        source_receipts = _sequence(data.get("source_receipts"), label="source_receipts")
        if not source_receipts:
            raise ValidationError("frontier fixture must declare source receipts")
        for index, receipt in enumerate(source_receipts, start=1):
            item = _mapping(receipt, label=f"source receipt {index}")
            _required_text(item.get("source_id"), field=f"source_receipts[{index}].source_id")
            _required_text(item.get("record_type"), field=f"source_receipts[{index}].record_type")
            _required_text(item.get("accession"), field=f"source_receipts[{index}].accession")
        _context_key(_mapping(data.get("context"), label="context"))
        pipelines = _mapping(data.get("pipelines"), label="pipelines")
        for name in self._pipeline_capabilities:
            _mapping(pipelines.get(name), label=f"pipelines.{name}")
        hardening = _mapping(data.get("hardening"), label="hardening")
        for operation in HARDENING_OPERATIONS:
            _mapping(hardening.get(operation), label=f"hardening.{operation}")
        controls = _sequence(data.get("negative_controls"), label="negative_controls")
        for index, control in enumerate(controls, start=1):
            item = _mapping(control, label=f"negative_controls[{index}]")
            _required_text(item.get("check_id"), field=f"negative_controls[{index}].check_id")
            _required_text(item.get("operation"), field=f"negative_controls[{index}].operation")
            _required_text(
                item.get("expected_state"), field=f"negative_controls[{index}].expected_state"
            )
            _mapping(item.get("payload"), label=f"negative_controls[{index}].payload")
        return data

    def evaluate_file(self, path: str | Path) -> FixtureEvaluationReport:
        """Load and evaluate one fixture from disk."""

        return self.evaluate(self.load_file(path))

    def evaluate(self, raw: Mapping[str, Any]) -> FixtureEvaluationReport:
        """Execute positive and negative fixture contracts."""

        data = self.validate_fixture(raw)
        fixture_id = _required_text(data.get("fixture_id"), field="fixture_id")
        fixture_version = _required_text(data.get("fixture_version"), field="fixture_version")
        context = _mapping(data.get("context"), label="context")
        context_key = _context_key(context)
        source_ids = tuple(
            sorted(
                _required_text(
                    _mapping(item, label="source receipt").get("source_id"), field="source_id"
                )
                for item in _sequence(data.get("source_receipts"), label="source_receipts")
            )
        )
        checks: list[FixtureCheck] = []
        contract_manifest = default_frontier_contract_registry().manifest()
        contract_ok = contract_manifest["contract_count"] == 79 and len(
            contract_manifest["capability_ids"]
        ) == 16
        self._append_state_check(
            checks,
            check_id="contract-boundary:frontier-inventory",
            capability_ids=(),
            expected_state=_ACCEPTED,
            observed_state=_ACCEPTED if contract_ok else "review",
            detail=(
                "frontier operation inventory is unique and maps all sixteen "
                "release capabilities"
            ),
            receipt=contract_manifest,
            extra_pass=contract_ok,
        )
        data_report = PublicFixtureCatalog.from_fixture(data).audit().to_dict()
        self._append_state_check(
            checks,
            check_id="data-boundary:public-catalog",
            capability_ids=(),
            expected_state="accepted",
            observed_state=str(data_report["state"]),
            detail=(
                "public fixture records have source receipts, exact context, and no sensitive paths"
            ),
            receipt=data_report,
            extra_pass=bool(data_report["accepted"]),
        )
        pipeline_reports: dict[str, Mapping[str, Any]] = {}
        operation_reports: dict[str, Mapping[str, Any]] = {}
        hardening_reports: dict[str, Mapping[str, Any]] = {}
        negative_reports: dict[str, Mapping[str, Any]] = {}

        pipelines = _mapping(data.get("pipelines"), label="pipelines")
        pipeline_reports["validation"] = self._run_pipeline(
            "validation",
            ValidationFrontierPipeline().run(
                _mapping(pipelines["validation"], label="validation pipeline"),
                pipeline_id=f"{fixture_id}:validation",
                context_key=context_key,
            ),
            checks,
        )
        pipeline_reports["evidence"] = self._run_pipeline(
            "evidence",
            EvidenceLifecyclePipeline().run(
                _mapping(pipelines["evidence"], label="evidence pipeline"),
                pipeline_id=f"{fixture_id}:evidence",
                context_key=context_key,
                signing_secret=_required_text(
                    _mapping(pipelines["evidence"], label="evidence pipeline").get(
                        "signing_secret"
                    ),
                    field="pipelines.evidence.signing_secret",
                ),
            ),
            checks,
        )
        pipeline_reports["workbench"] = self._run_pipeline(
            "workbench",
            WorkbenchQualityPipeline().run(
                _mapping(pipelines["workbench"], label="workbench pipeline"),
                pipeline_id=f"{fixture_id}:workbench",
                context_key=context_key,
                reviewer_id=_required_text(
                    _mapping(pipelines["workbench"], label="workbench pipeline").get("reviewer_id"),
                    field="pipelines.workbench.reviewer_id",
                ),
            ),
            checks,
        )
        pipeline_reports["deployment"] = self._run_pipeline(
            "deployment",
            DeploymentGovernancePipeline().run(
                _mapping(pipelines["deployment"], label="deployment pipeline"),
                pipeline_id=f"{fixture_id}:deployment",
                context_key=context_key,
            ),
            checks,
        )

        operation_reports = self._run_release_operations(
            pipelines, context_key=context_key, checks=checks
        )

        hardening = _mapping(data.get("hardening"), label="hardening")
        for operation in HARDENING_OPERATIONS:
            result = run_hardening_operation(
                operation,
                _mapping(hardening[operation], label=f"hardening.{operation}"),
                context_key=context_key,
            )
            serialized = result.to_dict()
            hardening_reports[operation] = serialized
            self._append_state_check(
                checks,
                check_id=f"hardening:{operation}",
                capability_ids=(),
                expected_state=_ACCEPTED,
                observed_state=_state(getattr(result, "state", _ACCEPTED)),
                detail=f"hardening operation {operation} completed with a deterministic receipt",
                receipt=serialized,
            )

        for control in _sequence(data.get("negative_controls"), label="negative_controls"):
            item = _mapping(control, label="negative control")
            check_id = _required_text(item.get("check_id"), field="check_id")
            operation = _required_text(item.get("operation"), field="operation")
            payload = _mapping(item.get("payload"), label=f"negative control {check_id} payload")
            expected = _required_text(
                item.get("expected_state"), field=f"{check_id}.expected_state"
            )
            result = run_end_to_end_operation(operation, payload, context_key=context_key)
            serialized = result.to_dict()
            negative_reports[check_id] = serialized
            expected_blocked = tuple(
                str(value) for value in item.get("expected_blocked_stage_ids", ())
            )
            observed_blocked = tuple(
                str(value) for value in getattr(result, "blocked_stage_ids", ())
            )
            blocked_ok = set(expected_blocked).issubset(set(observed_blocked))
            self._append_state_check(
                checks,
                check_id=f"negative:{check_id}",
                capability_ids=(),
                expected_state=expected,
                observed_state=_state(getattr(result, "state", "review")),
                detail=(
                    f"negative control {check_id} preserved the expected review boundary; "
                    f"blocked stages observed={','.join(observed_blocked) or 'none'}"
                ),
                receipt={"result": serialized, "blocked_ok": blocked_ok},
                extra_pass=blocked_ok,
            )

        passed = tuple(item.check_id for item in checks if item.passed)
        failed = tuple(item.check_id for item in checks if not item.passed)
        state = FrontierState.ACCEPTED if not failed else FrontierState.REVIEW
        boundary = _required_text(
            _mapping(data.get("provenance"), label="provenance").get("evidence_boundary"),
            field="provenance.evidence_boundary",
        )
        address_payload = {
            "fixture_id": fixture_id,
            "fixture_version": fixture_version,
            "context_key": context_key,
            "source_ids": source_ids,
            "contract_manifest": contract_manifest,
            "data_report": data_report,
            "checks": checks,
            "pipeline_reports": pipeline_reports,
            "operation_reports": operation_reports,
            "hardening_reports": hardening_reports,
            "negative_control_reports": negative_reports,
        }
        return FixtureEvaluationReport(
            fixture_id,
            fixture_version,
            context_key,
            source_ids,
            contract_manifest,
            data_report,
            pipeline_reports,
            operation_reports,
            hardening_reports,
            negative_reports,
            tuple(checks),
            passed,
            failed,
            state,
            boundary,
            _content_address(address_payload),
        )

    def _run_pipeline(
        self,
        name: str,
        report: FrontierPipelineReport,
        checks: list[FixtureCheck],
    ) -> Mapping[str, Any]:
        serialized = report.to_dict()
        stages = {stage["stage_id"]: stage for stage in serialized["stages"]}
        for stage_id, capability_id in self._pipeline_capabilities[name]:
            stage = stages.get(stage_id)
            if stage is None:
                self._append_state_check(
                    checks,
                    check_id=f"{name}:{stage_id}",
                    capability_ids=(capability_id,),
                    expected_state=_ACCEPTED,
                    observed_state="missing",
                    detail=f"pipeline {name} did not emit required stage {stage_id}",
                    receipt=serialized,
                )
                continue
            self._append_state_check(
                checks,
                check_id=f"{name}:{stage_id}",
                capability_ids=(capability_id,),
                expected_state=_ACCEPTED,
                observed_state=str(stage["state"]),
                detail=f"pipeline {name} emitted stage {stage_id} with a content address",
                receipt=stage,
                extra_pass=bool(stage.get("output_address")),
            )
        return serialized

    def _run_release_operations(
        self,
        pipelines: Mapping[str, Any],
        *,
        context_key: str,
        checks: list[FixtureCheck],
    ) -> dict[str, Mapping[str, Any]]:
        """Exercise every D13-D16 operation through the public adapter."""

        validation = _mapping(pipelines["validation"], label="validation pipeline")
        evidence = _mapping(pipelines["evidence"], label="evidence pipeline")
        workbench = _mapping(pipelines["workbench"], label="workbench pipeline")
        deployment = _mapping(pipelines["deployment"], label="deployment pipeline")
        package = _mapping(validation["package"], label="validation package")
        operation_inputs: dict[str, Mapping[str, Any]] = {
            "estimate-off-target-risk": {
                "records": validation["risk_records"],
                "review_threshold": 0.25,
                "blocking_threshold": 0.6,
            },
            "optimize-validation-voi": {
                "records": validation["voi_records"],
                "plan_id": "fixture-operation-voi",
                "budget": validation["budget"],
            },
            "export-experiment-package": {
                **package,
                "package_id": "fixture-operation-package",
            },
            "ingest-result-update-claims": {
                "claims": validation["claims"],
                "results": validation["results"],
            },
            "reclassify-evidence": {"records": evidence["claims"]},
            "manage-deprecation-supersession": {"records": evidence["supersession"]},
            "build-audit-reproducibility-bundle": {
                "sections": evidence["audit_sections"],
                "bundle_id": "fixture-operation-audit",
            },
            "publish-signed-dossier": {
                "payload": evidence["dossier"],
                "dossier_id": "fixture-operation-dossier",
                "key_id": evidence["key_id"],
                "signing_secret": evidence["signing_secret"],
                "audience": evidence["audience"],
            },
            "evaluate-structured-review": {
                "schema": workbench["form_schema"],
                "response": workbench["form_response"],
                "form_id": "fixture-operation-form",
                "reviewer_id": workbench["reviewer_id"],
            },
            "build-export-report": {
                "sections": workbench["report_sections"],
                "report_id": "fixture-operation-report",
                "format": workbench["report_format"],
            },
            "search-command-palette": {
                "records": workbench["records"],
                "query": workbench["query"],
                "commands": workbench["commands"],
            },
            "evaluate-accessibility-human-factors": {
                "surface": workbench["accessibility_surface"],
                "surface_id": "fixture-operation-surface",
            },
            "evaluate-privacy-security-policy": {
                "requests": deployment["requests"],
                "policies": deployment["policies"],
            },
            "build-local-deployment-bundle": {
                **_mapping(deployment["deployment"], label="deployment bundle"),
                "bundle_id": "fixture-operation-deployment",
                "platform": deployment["platform"],
                "runtime_version": deployment["runtime_version"],
                "offline": True,
            },
            "coordinate-federated-execution": {
                "tasks": deployment["tasks"],
                "sites": deployment["sites"],
                "plan_id": "fixture-operation-federation",
                "privacy_budget": deployment["privacy_budget"],
            },
            "decide-release-rollback": {
                "release_id": "fixture-operation-release",
                "current_version": deployment["current_version"],
                "requested_version": deployment["requested_version"],
                "checks": deployment["release_checks"],
                "action": deployment["release_action"],
            },
        }
        reports: dict[str, Mapping[str, Any]] = {}
        for operation in RELEASE_FRONTIER_OPERATIONS:
            if operation == "verify-signed-dossier":
                continue
            result = run_release_frontier_operation(
                operation, operation_inputs[operation], context_key=context_key
            )
            serialized = result.to_dict()
            reports[operation] = serialized
            self._append_state_check(
                checks,
                check_id=f"operation:{operation}",
                capability_ids=(),
                expected_state=_ACCEPTED,
                observed_state=_state(getattr(result, "state", _ACCEPTED)),
                detail=f"public operation adapter executed {operation}",
                receipt=serialized,
                extra_pass=bool(
                    serialized.get("content_address")
                    or serialized.get("manifest_address")
                    or serialized.get("dossier_address")
                    or serialized.get("report_address")
                    or serialized.get("aggregate_address")
                ),
            )

        verified = run_release_frontier_operation(
            "verify-signed-dossier",
            {
                "dossier": reports["publish-signed-dossier"],
                "signing_secret": evidence["signing_secret"],
                "audience": evidence["audience"][0],
            },
            context_key=context_key,
        )
        reports["verify-signed-dossier"] = verified.to_dict()
        self._append_state_check(
            checks,
            check_id="operation:verify-signed-dossier",
            capability_ids=(),
            expected_state=_ACCEPTED,
            observed_state=_state(getattr(verified, "state", "review")),
            detail="public operation adapter verified signed dossier audience and payload address",
            receipt=reports["verify-signed-dossier"],
            extra_pass=bool(getattr(verified, "valid_signature", False)),
        )
        return reports

    @staticmethod
    def _append_state_check(
        checks: list[FixtureCheck],
        *,
        check_id: str,
        capability_ids: tuple[str, ...],
        expected_state: str,
        observed_state: str,
        detail: str,
        receipt: Any,
        extra_pass: bool = True,
    ) -> None:
        checks.append(
            FixtureCheck(
                check_id,
                capability_ids,
                expected_state,
                observed_state,
                (
                    observed_state in _SUCCESS_STATES
                    if expected_state == _ACCEPTED
                    else observed_state == expected_state
                )
                and extra_pass,
                detail,
                _content_address(receipt),
            )
        )


def evaluate_frontier_fixture(path: str | Path) -> FixtureEvaluationReport:
    """Convenience function used by the CLI, CI, and downstream tests."""

    return FrontierFixtureEvaluator().evaluate_file(path)


__all__ = [
    "FIXTURE_SCHEMA_VERSION",
    "FixtureCheck",
    "FixtureEvaluationReport",
    "FrontierFixtureEvaluator",
    "evaluate_frontier_fixture",
]
