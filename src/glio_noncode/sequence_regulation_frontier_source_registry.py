"""Source registry and receipt matching for the C09-C12 fixture."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .sequence_regulation_frontier_public_data import (
    SequenceRegulationFixture,
    SequenceRegulationSourceReceipt,
    default_sequence_regulation_fixture,
)
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class SequenceRegulationSourceProfile:
    source_id: str
    display_name: str
    uri: str
    source_version: str
    source_kind: str
    coverage: tuple[str, ...]
    public_aggregate: bool = True
    checksum_basis: str = "declared_version_and_source_id"
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.source_id or not self.display_name or not self.source_version:
            raise ValidationError("source profile identity is incomplete")
        if not self.uri.startswith("https://"):
            raise ValidationError("source profile URI must use https")
        if not self.coverage or not self.public_aggregate:
            raise ValidationError("source profile must declare public coverage")
        if self.checksum_basis != "declared_version_and_source_id":
            raise ValidationError("unsupported checksum basis")
        if not self.content_address:
            object.__setattr__(
                self, "content_address", content_hash(self.to_dict(include_address=False))
            )

    @property
    def expected_checksum(self) -> str:
        return content_hash({"source_id": self.source_id, "version": self.source_version})

    def to_dict(self, *, include_address: bool = True) -> dict[str, Any]:
        result = {
            "source_id": self.source_id,
            "display_name": self.display_name,
            "uri": self.uri,
            "source_version": self.source_version,
            "source_kind": self.source_kind,
            "coverage": list(self.coverage),
            "public_aggregate": self.public_aggregate,
            "checksum_basis": self.checksum_basis,
            "expected_checksum": self.expected_checksum,
        }
        if include_address:
            result["content_address"] = self.content_address
        return result


@dataclass(frozen=True, slots=True)
class SequenceRegulationSourceMatch:
    source_id: str
    profile_address: str
    receipt_address: str
    identity_match: bool
    uri_match: bool
    version_match: bool
    checksum_match: bool
    context_match: bool
    accepted: bool
    detail: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.source_id or not self.profile_address or not self.receipt_address:
            raise ValidationError("source match is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceRegulationSourceRegistry:
    profiles: tuple[SequenceRegulationSourceProfile, ...]
    matches: tuple[SequenceRegulationSourceMatch, ...] = ()
    accepted: bool = False
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.profiles:
            raise ValidationError("source registry cannot be empty")
        if len({profile.source_id for profile in self.profiles}) != len(self.profiles):
            raise ValidationError("source IDs must be unique")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def profile(self, source_id: str) -> SequenceRegulationSourceProfile:
        for profile in self.profiles:
            if profile.source_id == source_id:
                return profile
        raise KeyError(source_id)

    def coverage_for(self, source_id: str) -> tuple[str, ...]:
        return self.profile(source_id).coverage

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "profiles": [profile.to_dict() for profile in self.profiles],
            "matches": [match.to_dict() for match in self.matches],
            "content_address": self.content_address,
        }


def default_sequence_regulation_source_profiles() -> tuple[SequenceRegulationSourceProfile, ...]:
    """Return the four declared public sources used by the fixture."""

    return (
        SequenceRegulationSourceProfile(
            "encode-regulation",
            "ENCODE regulatory reference",
            "https://www.encodeproject.org/",
            "2025.4",
            "regulatory_assay_catalog",
            ("splice_regulation", "utr_regulation", "nucleosome_propensity"),
        ),
        SequenceRegulationSourceProfile(
            "jaspar-motifs",
            "JASPAR motif reference",
            "https://jaspar.genereg.net/",
            "2026.1",
            "motif_catalog",
            ("splice_regulation", "promoter_grammar"),
        ),
        SequenceRegulationSourceProfile(
            "ncbi-reference",
            "NCBI reference sequence portal",
            "https://www.ncbi.nlm.nih.gov/",
            "2026.1",
            "reference_sequence",
            ("nucleosome_propensity", "utr_regulation"),
        ),
        SequenceRegulationSourceProfile(
            "ensembl-reference",
            "Ensembl reference portal",
            "https://www.ensembl.org/",
            "release-114",
            "reference_annotation",
            ("nucleosome_propensity", "promoter_grammar"),
        ),
    )


def _match(
    profile: SequenceRegulationSourceProfile,
    receipt: SequenceRegulationSourceReceipt,
    context_key: str,
) -> SequenceRegulationSourceMatch:
    identity = profile.source_id == receipt.source_id
    uri = profile.uri == receipt.uri
    version = profile.source_version == receipt.source_version
    checksum = profile.expected_checksum == receipt.checksum
    context = receipt.context_key == context_key
    accepted = (
        identity
        and uri
        and version
        and checksum
        and context
        and receipt.public_aggregate
        and not receipt.patient_level
    )
    detail = "source profile and receipt match" if accepted else "source profile and receipt differ"
    return SequenceRegulationSourceMatch(
        profile.source_id,
        profile.content_address,
        receipt.content_address,
        identity,
        uri,
        version,
        checksum,
        context,
        accepted,
        detail,
    )


def build_sequence_regulation_source_registry(
    fixture: SequenceRegulationFixture | None = None,
) -> SequenceRegulationSourceRegistry:
    """Match every fixture receipt to a declared profile."""

    fixture = fixture or default_sequence_regulation_fixture()
    profiles = default_sequence_regulation_source_profiles()
    profile_by_id = {profile.source_id: profile for profile in profiles}
    matches = tuple(
        _match(profile_by_id[receipt.source_id], receipt, fixture.context_key)
        for receipt in fixture.sources
        if receipt.source_id in profile_by_id
    )
    accepted = len(matches) == len(fixture.sources) == len(profiles) and all(
        match.accepted for match in matches
    )
    body = {"profiles": profiles, "matches": matches, "accepted": accepted}
    return SequenceRegulationSourceRegistry(profiles, matches, accepted, content_hash(body))


def verify_sequence_regulation_source_registry(
    registry: SequenceRegulationSourceRegistry,
) -> tuple[str, ...]:
    """Return stable failure IDs for source registry review."""

    failures: list[str] = []
    if not registry.accepted:
        failures.append("registry_not_accepted")
    for match in registry.matches:
        if not match.identity_match:
            failures.append(f"{match.source_id}:identity")
        if not match.uri_match:
            failures.append(f"{match.source_id}:uri")
        if not match.version_match:
            failures.append(f"{match.source_id}:version")
        if not match.checksum_match:
            failures.append(f"{match.source_id}:checksum")
        if not match.context_match:
            failures.append(f"{match.source_id}:context")
    return tuple(failures)


__all__ = [
    "SequenceRegulationSourceMatch",
    "SequenceRegulationSourceProfile",
    "SequenceRegulationSourceRegistry",
    "build_sequence_regulation_source_registry",
    "default_sequence_regulation_source_profiles",
    "verify_sequence_regulation_source_registry",
]
