"""End-to-end composition pipelines for the D13-D16 frontier controls."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .frontier_data_alpha import (
    FrontierIssue,
    FrontierState,
    _address,
    _mapping,
    _required_text,
    _text,
)
from .frontier_release_alpha import (
    AccessibilityHumanFactorsLayer,
    AuditReproducibilityBundleBuilder,
    DeprecationSupersessionManager,
    ExperimentPackageExporter,
    ExportReportBuilder,
    FederatedExecutionCoordinator,
    GlobalSearchCommandPalette,
    LocalDeploymentBundleBuilder,
    OffTargetRiskEstimator,
    PrivacySecurityPolicyEngine,
    ReclassificationEngine,
    ReleaseRollbackController,
    ResultIngestionClaimUpdater,
    SignedDossierPublisher,
    StructuredReviewForm,
    ValidationValueOfInformationOptimizer,
)
from .frontier_release_hardening import (
    DeploymentDependencyResolver,
    EvidenceGraphIntegrityAuditor,
    EvidenceLineageBuilder,
    FederatedPrivacyAccountant,
    HumanFactorsScenarioSimulator,
    ValidationExecutionReadinessChecker,
)
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class PipelineStage:
    stage_id: str
    state: FrontierState
    output_address: str
    issue_codes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FrontierPipelineReport:
    pipeline_id: str
    context_key: str
    stages: tuple[PipelineStage, ...]
    completed_stage_ids: tuple[str, ...]
    blocked_stage_ids: tuple[str, ...]
    state: FrontierState
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _stage(stage_id: str, result: Any) -> PipelineStage:
    raw_state = getattr(result, "state", None)
    if raw_state is None:
        has_review = bool(
            getattr(result, "review_ids", ())
            or getattr(result, "failed_ids", ())
            or getattr(result, "abstained_ids", ())
            or getattr(result, "denied_ids", ())
        )
        raw_state = FrontierState.REVIEW if has_review else FrontierState.ACCEPTED
    if isinstance(raw_state, FrontierState):
        state = raw_state
    elif str(raw_state) in {"ready", "released", "rolled_back"}:
        state = FrontierState.ACCEPTED
    elif str(raw_state) in {item.value for item in FrontierState}:
        state = FrontierState(str(raw_state))
    else:
        state = FrontierState.REVIEW
    issues: list[str] = []
    for item in getattr(result, "issues", ()):
        issues.append(str(getattr(item, "code", item)))
    for item in getattr(result, "failed_ids", ()):
        issues.append(str(item))
    for item in getattr(result, "review_ids", ()):
        issues.append(str(item))
    address = str(
        getattr(
            result,
            "content_address",
            getattr(result, "manifest_address", getattr(result, "bundle_address", "")),
        )
    )
    return PipelineStage(stage_id, state, address, tuple(sorted(set(issues))))


def _report(
    pipeline_id: str, context_key: str, results: Sequence[tuple[str, Any]]
) -> FrontierPipelineReport:
    stages = tuple(_stage(stage_id, result) for stage_id, result in results)
    completed = tuple(
        item.stage_id
        for item in stages
        if item.state in {FrontierState.ACCEPTED, FrontierState.PUBLISHED}
    )
    blocked = tuple(
        item.stage_id
        for item in stages
        if item.state not in {FrontierState.ACCEPTED, FrontierState.PUBLISHED}
    )
    state = FrontierState.ACCEPTED if not blocked else FrontierState.REVIEW
    return FrontierPipelineReport(
        pipeline_id, context_key, stages, completed, blocked, state, _address(stages)
    )


class ValidationFrontierPipeline:
    """Compose risk, value, package, readiness, and claim-update stages."""

    def run(
        self,
        payload: Mapping[str, Any],
        *,
        pipeline_id: str,
        context_key: str,
    ) -> FrontierPipelineReport:
        pipeline_id = _required_text(pipeline_id, field="pipeline_id")
        context_key = _required_text(context_key, field="context_key")
        data = _mapping(payload, label="validation pipeline payload")
        risk = OffTargetRiskEstimator().estimate(
            data.get("risk_records", data.get("records", ())), context_key=context_key
        )
        voi = (
            ValidationValueOfInformationOptimizer().optimize(
                data.get("voi_records", ()),
                plan_id=f"{pipeline_id}:voi",
                context_key=context_key,
                budget=float(data.get("budget", 0.0)),
            )
            if data.get("voi_records")
            else _EmptyPipelineStage("voi")
        )
        package_payload = data.get(
            "package",
            {
                "experiments": data.get("experiments", ()),
                "controls": data.get("controls", ()),
                "protocols": data.get("protocols", ()),
            },
        )
        package = ExperimentPackageExporter().export(
            package_payload, package_id=f"{pipeline_id}:package", context_key=context_key
        )
        readiness = ValidationExecutionReadinessChecker().evaluate(
            package_payload,
            package_id=package.package_id,
            context_key=context_key,
            required_controls=data.get("required_controls", ()),
            required_outputs=data.get("required_outputs", ()),
        )
        claims = (
            ResultIngestionClaimUpdater().update(
                data.get("claims", ()), data.get("results", ()), context_key=context_key
            )
            if data.get("results")
            else _EmptyPipelineStage("claim_update")
        )
        return _report(
            pipeline_id,
            context_key,
            (
                ("off_target_risk", risk),
                ("value_of_information", voi),
                ("experiment_package", package),
                ("execution_readiness", readiness),
                ("claim_update", claims),
            ),
        )


class EvidenceLifecyclePipeline:
    """Compose graph integrity, lineage, reclassification, audit, and signing."""

    def run(
        self,
        payload: Mapping[str, Any],
        *,
        pipeline_id: str,
        context_key: str,
        signing_secret: str,
    ) -> FrontierPipelineReport:
        pipeline_id = _required_text(pipeline_id, field="pipeline_id")
        context_key = _required_text(context_key, field="context_key")
        signing_secret = _required_text(signing_secret, field="signing_secret")
        data = _mapping(payload, label="evidence pipeline payload")
        graph = EvidenceGraphIntegrityAuditor().audit(
            data.get("nodes", ()), data.get("edges", ()), context_key=context_key
        )
        lineage = (
            EvidenceLineageBuilder().build(data.get("lineage", ()), context_key=context_key)
            if data.get("lineage")
            else _EmptyPipelineStage("lineage")
        )
        reclassification = (
            ReclassificationEngine().reclassify(data.get("claims", ()), context_key=context_key)
            if data.get("claims")
            else _EmptyPipelineStage("reclassification")
        )
        supersession = (
            DeprecationSupersessionManager().manage(
                data.get("supersession", ()), context_key=context_key
            )
            if data.get("supersession")
            else _EmptyPipelineStage("supersession")
        )
        audit = AuditReproducibilityBundleBuilder().build(
            data.get(
                "audit_sections",
                {
                    "evidence": data.get("nodes", ()),
                    "review": data.get("claims", ()),
                    "release": data.get("release", ()),
                },
            ),
            bundle_id=f"{pipeline_id}:audit",
            context_key=context_key,
        )
        dossier = SignedDossierPublisher().publish(
            data.get("dossier", {"pipeline_id": pipeline_id}),
            dossier_id=f"{pipeline_id}:dossier",
            context_key=context_key,
            key_id=_required_text(data.get("key_id", "pipeline-key"), field="key_id"),
            signing_secret=signing_secret,
            audience=data.get("audience", ()),
        )
        return _report(
            pipeline_id,
            context_key,
            (
                ("graph_integrity", graph),
                ("lineage", lineage),
                ("reclassification", reclassification),
                ("supersession", supersession),
                ("audit_bundle", audit),
                ("signed_dossier", dossier),
            ),
        )


class WorkbenchQualityPipeline:
    """Compose review form, report, search, accessibility, and human-factors checks."""

    def run(
        self,
        payload: Mapping[str, Any],
        *,
        pipeline_id: str,
        context_key: str,
        reviewer_id: str,
    ) -> FrontierPipelineReport:
        pipeline_id = _required_text(pipeline_id, field="pipeline_id")
        context_key = _required_text(context_key, field="context_key")
        reviewer_id = _required_text(reviewer_id, field="reviewer_id")
        data = _mapping(payload, label="workbench pipeline payload")
        form = StructuredReviewForm().evaluate(
            data.get("form_schema", ()),
            data.get("form_response", {}),
            form_id=f"{pipeline_id}:form",
            context_key=context_key,
            reviewer_id=reviewer_id,
        )
        report = ExportReportBuilder().build(
            data.get("report_sections", ()),
            report_id=f"{pipeline_id}:report",
            context_key=context_key,
            format=_text(data.get("report_format", "json"), field="report_format") or "json",
        )
        search = GlobalSearchCommandPalette().search(
            data.get("records", ()),
            query=_required_text(data.get("query", ""), field="query"),
            commands=data.get("commands", ()),
        )
        accessibility = AccessibilityHumanFactorsLayer().evaluate(
            data.get("accessibility_surface", {}), surface_id=f"{pipeline_id}:surface"
        )
        human = HumanFactorsScenarioSimulator().simulate(
            data.get("human_factors_events", ()), scenario_id=f"{pipeline_id}:scenario"
        )
        return _report(
            pipeline_id,
            context_key,
            (
                ("structured_review", form),
                ("report_export", report),
                ("search_palette", search),
                ("accessibility", accessibility),
                ("human_factors", human),
            ),
        )


class DeploymentGovernancePipeline:
    """Compose security, dependencies, privacy, federation, and release gates."""

    def run(
        self,
        payload: Mapping[str, Any],
        *,
        pipeline_id: str,
        context_key: str,
    ) -> FrontierPipelineReport:
        pipeline_id = _required_text(pipeline_id, field="pipeline_id")
        context_key = _required_text(context_key, field="context_key")
        data = _mapping(payload, label="deployment pipeline payload")
        security = PrivacySecurityPolicyEngine().evaluate(
            data.get("requests", ()), context_key=context_key, policies=data.get("policies", {})
        )
        dependencies = DeploymentDependencyResolver().resolve(data.get("services", ()))
        privacy = FederatedPrivacyAccountant().account(
            data.get("privacy_requests", ()),
            epsilon_budget=float(data.get("epsilon_budget", 0.0)),
            delta_budget=float(data.get("delta_budget", 0.0)),
        )
        deployment = LocalDeploymentBundleBuilder().build(
            data.get("deployment", data),
            bundle_id=f"{pipeline_id}:deployment",
            platform=_required_text(data.get("platform", "local"), field="platform"),
            runtime_version=_required_text(
                data.get("runtime_version", "python"), field="runtime_version"
            ),
        )
        federated = FederatedExecutionCoordinator().coordinate(
            data.get("tasks", ()),
            data.get("sites", ()),
            plan_id=f"{pipeline_id}:federated",
            context_key=context_key,
            privacy_budget=int(data.get("privacy_budget", 0)),
        )
        release = ReleaseRollbackController().decide(
            release_id=f"{pipeline_id}:release",
            current_version=_required_text(
                data.get("current_version", "0"), field="current_version"
            ),
            requested_version=_required_text(
                data.get("requested_version", "1"), field="requested_version"
            ),
            checks=data.get("release_checks", {}),
            action=_text(data.get("release_action", "release"), field="release_action")
            or "release",
            previous_version=_text(data.get("previous_version"), field="previous_version") or None,
        )
        return _report(
            pipeline_id,
            context_key,
            (
                ("security_policy", security),
                ("dependency_resolution", dependencies),
                ("privacy_accounting", privacy),
                ("deployment_bundle", deployment),
                ("federated_execution", federated),
                ("release_rollback", release),
            ),
        )


@dataclass(frozen=True, slots=True)
class _EmptyPipelineStage:
    stage_id: str
    state: FrontierState = FrontierState.ACCEPTED
    content_address: str = "sha256:empty"
    issues: tuple[FrontierIssue, ...] = ()


def run_end_to_end_operation(
    operation: str, payload: Mapping[str, Any], *, context_key: str | None = None
) -> FrontierPipelineReport:
    """Run one end-to-end frontier composition pipeline."""

    operation = _required_text(operation, field="operation")
    data = _mapping(payload, label="pipeline payload")
    context = context_key or _required_text(data.get("context_key"), field="context_key")
    pipeline_id = _required_text(data.get("pipeline_id"), field="pipeline_id")
    if operation == "run-validation-frontier-pipeline":
        return ValidationFrontierPipeline().run(data, pipeline_id=pipeline_id, context_key=context)
    if operation == "run-evidence-lifecycle-pipeline":
        return EvidenceLifecyclePipeline().run(
            data,
            pipeline_id=pipeline_id,
            context_key=context,
            signing_secret=_required_text(data.get("signing_secret"), field="signing_secret"),
        )
    if operation == "run-workbench-quality-pipeline":
        return WorkbenchQualityPipeline().run(
            data,
            pipeline_id=pipeline_id,
            context_key=context,
            reviewer_id=_required_text(data.get("reviewer_id"), field="reviewer_id"),
        )
    if operation == "run-deployment-governance-pipeline":
        return DeploymentGovernancePipeline().run(
            data, pipeline_id=pipeline_id, context_key=context
        )
    raise ValidationError(f"unknown end-to-end operation: {operation}")


END_TO_END_OPERATIONS = (
    "run-validation-frontier-pipeline",
    "run-evidence-lifecycle-pipeline",
    "run-workbench-quality-pipeline",
    "run-deployment-governance-pipeline",
)
