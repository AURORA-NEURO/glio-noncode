"""Human-readable reports that preserve typed evidence and uncertainty."""

from __future__ import annotations

from dataclasses import dataclass

from .models import Dossier, EvidenceState, Hypothesis
from .serialization import canonical_json


@dataclass(frozen=True, slots=True)
class DossierSummary:
    case_id: str
    run_id: str
    status: str
    hypothesis_count: int
    evidence_count: int
    supported_claim_count: int
    negative_claim_count: int
    missing_claim_count: int
    top_hypothesis_id: str | None
    top_support: float | None
    top_uncertainty: float | None
    recommended_experiment_id: str | None
    warning_count: int

    def to_dict(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "run_id": self.run_id,
            "status": self.status,
            "hypothesis_count": self.hypothesis_count,
            "evidence_count": self.evidence_count,
            "supported_claim_count": self.supported_claim_count,
            "negative_claim_count": self.negative_claim_count,
            "missing_claim_count": self.missing_claim_count,
            "top_hypothesis_id": self.top_hypothesis_id,
            "top_support": self.top_support,
            "top_uncertainty": self.top_uncertainty,
            "recommended_experiment_id": self.recommended_experiment_id,
            "warning_count": self.warning_count,
        }


def summarize(dossier: Dossier) -> DossierSummary:
    """Create a compact view without hiding the full dossier."""

    top = dossier.hypotheses[0] if dossier.hypotheses else None
    return DossierSummary(
        case_id=dossier.case_id,
        run_id=dossier.run_id,
        status=dossier.status.value,
        hypothesis_count=len(dossier.hypotheses),
        evidence_count=len(dossier.evidence),
        supported_claim_count=sum(claim.state == EvidenceState.SUPPORTED for claim in dossier.evidence),
        negative_claim_count=sum(claim.state in (EvidenceState.MEASURED_NEGATIVE, EvidenceState.CONTRADICTORY) for claim in dossier.evidence),
        missing_claim_count=sum(claim.state in (EvidenceState.UNSUPPORTED, EvidenceState.ABSTAINED, EvidenceState.OUT_OF_DOMAIN) for claim in dossier.evidence),
        top_hypothesis_id=top.hypothesis_id if top else None,
        top_support=top.support if top else None,
        top_uncertainty=top.uncertainty if top else None,
        recommended_experiment_id=dossier.experiments[0].option_id if dossier.experiments else None,
        warning_count=len(dossier.warnings),
    )


def render_markdown(dossier: Dossier) -> str:
    """Render a review-oriented dossier without promotional or clinical language."""

    lines = [
        f"# Research Dossier: `{dossier.case_id}`",
        "",
        f"- Status: `{dossier.status.value}`",
        f"- Run: `{dossier.run_id}`",
        f"- Research-use only: `{str(dossier.research_use_only).lower()}`",
        f"- Policy: `{dossier.policy_version}`",
        f"- Input: `{dossier.input_address}`",
        f"- Content: `{dossier.content_address}`",
        "",
        "## Hypotheses",
        "",
    ]
    for index, hypothesis in enumerate(dossier.hypotheses, start=1):
        lines.extend(
            [
                f"### {index}. `{hypothesis.hypothesis_id}`",
                f"- Variant: `{hypothesis.variant_id}`",
                f"- Element: `{hypothesis.element_id}`",
                f"- Gene: `{hypothesis.gene_id}`",
                f"- State: `{hypothesis.state_id}`",
                f"- Support: `{hypothesis.support:.3f}`",
                f"- Uncertainty: `{hypothesis.uncertainty:.3f}`",
                f"- Mechanism: {hypothesis.mechanism}",
                f"- Missing evidence: {len(hypothesis.missing_evidence)}",
                f"- Negative evidence: {len(hypothesis.negative_evidence)}",
                "",
            ]
        )
        for edge in hypothesis.edges:
            lines.append(f"  - `{edge.edge_type.value}` `{edge.source_id}` → `{edge.target_id}`; support `{edge.support:.3f}`; uncertainty `{edge.uncertainty:.3f}`")
        lines.append("")
    lines.extend(["## Evidence ledger", ""])
    for claim in dossier.evidence:
        lines.append(f"- `{claim.evidence_id}` `{claim.state.value}` `{claim.channel}`: {claim.summary}")
    lines.extend(["", "## Validation routes", ""])
    for option in dossier.experiments:
        lines.extend(
            [
                f"- `{option.option_id}` `{option.assay.value}` priority `{option.priority:.3f}`",
                f"  - Readouts: {', '.join(option.readouts)}",
                f"  - Controls: {', '.join(option.controls)}",
                f"  - Limitations: {', '.join(option.limitations)}",
            ]
        )
    if dossier.warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in dossier.warnings)
    lines.append("")
    return "\n".join(lines)


def render_json(dossier: Dossier) -> str:
    """Return canonical JSON for archival export."""

    return canonical_json(dossier.to_dict())
