"""Declared thresholds for sequence grammar review and quality gates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class SequenceGrammarThresholdProfile:
    threshold_id: str
    metric: str
    operator: str
    value: float
    rationale: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if (
            not self.threshold_id.strip()
            or not self.metric.strip()
            or self.operator not in {">=", "<=", "=="}
        ):
            raise ValidationError("threshold profile is invalid")
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {
                        "threshold_id": self.threshold_id,
                        "metric": self.metric,
                        "operator": self.operator,
                        "value": self.value,
                        "rationale": self.rationale,
                    }
                ),
            )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceGrammarThresholdReport:
    accepted: bool
    profiles: tuple[SequenceGrammarThresholdProfile, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if len(self.profiles) != 6:
            raise ValidationError("six threshold profiles are required")
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash({"accepted": self.accepted, "profiles": self.profiles}),
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "profile_count": len(self.profiles),
            "profiles": [profile.to_dict() for profile in self.profiles],
            "content_address": self.content_address,
        }


def default_sequence_grammar_threshold_profiles() -> tuple[SequenceGrammarThresholdProfile, ...]:
    rows = (
        ("T01", "fixture_positive_count", ">=", 4.0, "four positive operation paths"),
        ("T02", "fixture_control_count", ">=", 12.0, "twelve matched controls"),
        ("T03", "evaluation_check_pass_rate", "==", 1.0, "all deterministic checks pass"),
        ("T04", "source_receipt_count", "==", 4.0, "four public source receipts"),
        ("T05", "review_queue_count", "==", 12.0, "all controls remain reviewable"),
        ("T06", "clinical_probability_claims", "==", 0.0, "no probability conversion is permitted"),
    )
    return tuple(SequenceGrammarThresholdProfile(*row) for row in rows)


def build_sequence_grammar_threshold_report() -> SequenceGrammarThresholdReport:
    profiles = default_sequence_grammar_threshold_profiles()
    return SequenceGrammarThresholdReport(
        all(profile.content_address.startswith("sha256:") for profile in profiles), profiles
    )


__all__ = [
    "SequenceGrammarThresholdProfile",
    "SequenceGrammarThresholdReport",
    "build_sequence_grammar_threshold_report",
    "default_sequence_grammar_threshold_profiles",
]
