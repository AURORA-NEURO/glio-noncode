"""Input, graph, and release validation with explainable issue codes."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from .models import CaseManifest, Dossier, EvidenceState, ResearchStatus, ReviewState
from .policy import ResearchPolicy


class IssueSeverity(str, Enum):
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
                    "Normalize all variants to the declared case build or create an explicit lift-over stage.",
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
        for index, hypothesis in enumerate(dossier.hypotheses):
            claim_ids = {claim.evidence_id for claim in dossier.evidence}
            for edge in hypothesis.edges:
                missing = set(edge.claim_ids) - claim_ids
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
