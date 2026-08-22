"""Boundary threshold probes for deterministic sequence-effect adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class SequenceEffectThresholdProfile:
    threshold_id: str
    metric: str
    lower: float
    upper: float
    unit: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if self.lower > self.upper:
            raise ValueError("threshold lower bound cannot exceed upper bound")
        if not self.content_address:
            object.__setattr__(
                self, "content_address", content_hash(jsonable(self) | {"content_address": ""})
            )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceEffectThresholdReport:
    profiles: tuple[SequenceEffectThresholdProfile, ...]
    probes: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {"profiles": self.profiles, "probes": self.probes, "accepted": self.accepted}
                ),
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "profile_count": len(self.profiles),
            "probe_count": len(self.probes),
            "profiles": [item.to_dict() for item in self.profiles],
            "probes": list(self.probes),
            "content_address": self.content_address,
        }


def default_sequence_effect_threshold_profiles() -> tuple[SequenceEffectThresholdProfile, ...]:
    return (
        SequenceEffectThresholdProfile("gc-fraction", "gc_fraction", 0.0, 1.0, "fraction"),
        SequenceEffectThresholdProfile(
            "ambiguity-fraction", "ambiguous_fraction", 0.0, 1.0, "fraction"
        ),
        SequenceEffectThresholdProfile(
            "long-context", "context_length", 1024.0, 1000000.0, "base_pairs"
        ),
        SequenceEffectThresholdProfile("ensemble-spread", "disagreement", 0.0, 0.25, "delta_units"),
        SequenceEffectThresholdProfile(
            "model-uncertainty", "reported_uncertainty", 0.0, 1.0, "fraction"
        ),
        SequenceEffectThresholdProfile("kmer-size", "kmer_size", 1.0, 8.0, "bases"),
    )


def build_sequence_effect_threshold_report() -> SequenceEffectThresholdReport:
    profiles = default_sequence_effect_threshold_profiles()
    probes = tuple(
        {
            "threshold_id": profile.threshold_id,
            "values": [profile.lower, (profile.lower + profile.upper) / 2, profile.upper],
            "boundary_inclusive": True,
        }
        for profile in profiles
    )
    return SequenceEffectThresholdReport(
        profiles, probes, all(len(item["values"]) == 3 for item in probes)
    )


__all__ = [
    "SequenceEffectThresholdProfile",
    "SequenceEffectThresholdReport",
    "build_sequence_effect_threshold_report",
    "default_sequence_effect_threshold_profiles",
]
