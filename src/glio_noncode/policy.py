"""Research-use policy enforcement and claim-language checks."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from .errors import PolicyViolation
from .models import Dossier, ResearchStatus


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    """Result of applying the product boundary to a payload."""

    allowed: bool
    policy_version: str
    violations: tuple[str, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "allowed": self.allowed,
            "policy_version": self.policy_version,
            "violations": list(self.violations),
            "warnings": list(self.warnings),
        }


class ResearchPolicy:
    """Enforce a research-only boundary before output is released."""

    version = "research-boundary-2026.08"

    _blocked_patterns = (
        (re.compile(r"\bdiagnos(?:e|is|tic|ing)\b", re.IGNORECASE), "diagnostic claim"),
        (re.compile(r"\b(?:treat|treatment|therapy)\s+recommend", re.IGNORECASE), "treatment recommendation"),
        (re.compile(r"\bpathogenic(?:ity|)\b", re.IGNORECASE), "pathogenicity claim"),
        (re.compile(r"\btrial\s+eligib", re.IGNORECASE), "trial eligibility claim"),
        (re.compile(r"\bclinically\s+actionable\b", re.IGNORECASE), "clinical actionability claim"),
        (re.compile(r"\bpatient\s+specific\b", re.IGNORECASE), "patient-specific claim"),
    )

    def inspect_texts(self, texts: Iterable[str]) -> PolicyDecision:
        violations: list[str] = []
        for text in texts:
            for pattern, label in self._blocked_patterns:
                if pattern.search(text):
                    violations.append(label)
        unique = tuple(dict.fromkeys(violations))
        warnings = ("All outputs are research-use only and require expert review.",)
        return PolicyDecision(
            allowed=not unique,
            policy_version=self.version,
            violations=unique,
            warnings=warnings,
        )

    def enforce_texts(self, texts: Iterable[str]) -> PolicyDecision:
        decision = self.inspect_texts(texts)
        if not decision.allowed:
            raise PolicyViolation("; ".join(decision.violations))
        return decision

    def validate_dossier(self, dossier: Dossier) -> PolicyDecision:
        texts = [
            dossier.case_id,
            *(hypothesis.mechanism for hypothesis in dossier.hypotheses),
            *(claim.summary for claim in dossier.evidence),
            *dossier.warnings,
        ]
        decision = self.inspect_texts(texts)
        violations = list(decision.violations)
        if not dossier.research_use_only:
            violations.append("research-use flag missing")
        if dossier.status == ResearchStatus.RELEASED_RESEARCH and dossier.review is None:
            violations.append("released dossier has no review decision")
        return PolicyDecision(
            allowed=not violations,
            policy_version=self.version,
            violations=tuple(dict.fromkeys(violations)),
            warnings=decision.warnings,
        )
