"""Input, graph, and release validation with explainable issue codes."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .errors import ValidationError
from .models import (
    CaseManifest,
    Dossier,
    EvidenceState,
    HypothesisEdge,
    ResearchStatus,
    ReviewState,
)
from .policy import ResearchPolicy
from .serialization import canonical_bytes, content_hash


def _is_content_address(value: str) -> bool:
    prefix, separator, digest = value.rpartition(":")
    return (
        separator == ":"
        and bool(prefix)
        and len(digest) == 64
        and all(character in "0123456789abcdef" for character in digest)
    )


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

    def to_dict(self) -> dict[str, object]:
        return {"valid": self.valid, "issues": [issue.to_dict() for issue in self.issues]}


class ContractValidator:
    """Validate things not fully captured by dataclass constructors."""

    def validate_manifest(self, manifest: CaseManifest) -> ValidationReport:
        issues: list[ValidationIssue] = []
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
        return ValidationReport(
            valid=not any(issue.severity == IssueSeverity.ERROR for issue in issues),
            issues=tuple(issues),
        )

    def validate_dossier(self, dossier: Dossier) -> ValidationReport:
        issues: list[ValidationIssue] = []
        canonical_body = {
            key: value
            for key, value in dossier.to_dict().items()
            if key != "content_address"
        }
        if dossier.content_address != content_hash(canonical_body):
            issues.append(
                ValidationIssue(
                    "dossier_address_mismatch",
                    IssueSeverity.ERROR,
                    "Dossier content address does not match its canonical payload.",
                    "content_address",
                    "Rebuild the dossier from its canonical fields before review or release.",
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
        evidence_positions = {
            claim.evidence_id: index for index, claim in enumerate(dossier.evidence)
        }
        for index, claim in enumerate(dossier.evidence):
            bad_dependencies = tuple(
                dependency
                for dependency in claim.depends_on
                if (
                    dependency not in evidence_positions
                    and not _is_content_address(dependency)
                )
                or evidence_positions.get(dependency, -1) >= index
            )
            if bad_dependencies:
                issues.append(
                    ValidationIssue(
                        "invalid_evidence_dependency",
                        IssueSeverity.ERROR,
                        "Evidence claim has dangling, forward, or cyclic dependencies: "
                        f"{sorted(bad_dependencies)}.",
                        f"evidence[{index}].depends_on",
                        "Depend only on earlier ledger claims or canonical source addresses.",
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
                    if claim_id in claims_by_id
                    and claims_by_id[claim_id].edge_id != edge.edge_id
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
            unknown_hypotheses = set(dossier.review.reviewed_hypothesis_ids) - set(
                hypothesis_ids
            )
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
        if dossier.status == ResearchStatus.RELEASED_RESEARCH:
            if dossier.review is None or dossier.review.state != ReviewState.ACCEPTED:
                issues.append(
                    ValidationIssue(
                        "release_without_acceptance",
                        IssueSeverity.ERROR,
                        "Released dossier is not backed by an accepted review.",
                        "review",
                        "Record an accepted review that names the hypotheses and checked claims.",
                    )
                )
            if any(claim.state == EvidenceState.ABSTAINED for claim in dossier.evidence):
                issues.append(
                    ValidationIssue(
                        "released_abstention",
                        IssueSeverity.WARNING,
                        "Released dossier contains abstained evidence.",
                        "evidence[*].state",
                        "Keep the abstention visible and document why the dossier remains useful.",
                    )
                )
        return ValidationReport(
            valid=not any(issue.severity == IssueSeverity.ERROR for issue in issues),
            issues=tuple(issues),
        )


class ReleaseGate:
    """Combine structural checks and policy checks before a release transition."""

    def __init__(self, policy: ResearchPolicy | None = None) -> None:
        self.policy = policy or ResearchPolicy()
        self.validator = ContractValidator()

    def check(self, dossier: Dossier) -> ValidationReport:
        structural = self.validator.validate_dossier(dossier)
        policy = self.policy.validate_dossier(dossier)
        issues = list(structural.issues)
        issues.extend(
            ValidationIssue(
                "policy_violation",
                IssueSeverity.ERROR,
                violation,
                "policy",
                "Remove the prohibited claim or keep the dossier unreleased.",
            )
            for violation in policy.violations
        )
        return ValidationReport(
            valid=not any(issue.severity == IssueSeverity.ERROR for issue in issues),
            issues=tuple(issues),
        )
