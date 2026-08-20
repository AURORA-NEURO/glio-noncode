"""Reference assembly registry and explicit coordinate projection contracts."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .models import VariantIdentity, VariantKind
from .serialization import content_hash, jsonable


class CoordinateSystem(StrEnum):
    """Coordinate convention used by a source or mapping."""

    ONE_BASED_INCLUSIVE = "one_based_inclusive"
    ZERO_BASED_HALF_OPEN = "zero_based_half_open"


class ProjectionStatus(StrEnum):
    """Outcome of an explicit reference projection."""

    IDENTITY = "identity"
    MAPPED = "mapped"
    ABSTAINED = "abstained"
    PARTIAL = "partial"


@dataclass(frozen=True, slots=True)
class ReferenceAssembly:
    """Stable assembly identity and public source metadata."""

    assembly_id: str
    canonical_name: str
    species: str
    release: str
    aliases: tuple[str, ...]
    coordinate_system: CoordinateSystem = CoordinateSystem.ONE_BASED_INCLUSIVE
    source_ids: tuple[str, ...] = ()
    accession: str | None = None

    def __post_init__(self) -> None:
        for name in ("assembly_id", "canonical_name", "species", "release"):
            if not str(getattr(self, name)).strip():
                raise ValidationError(f"{name} must not be empty")
        if not self.aliases:
            raise ValidationError("reference assembly requires at least one alias")

    def matches(self, value: str) -> bool:
        normalized = value.strip().lower()
        return normalized in {
            self.assembly_id.lower(),
            self.canonical_name.lower(),
        } or normalized in {alias.lower() for alias in self.aliases}

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MappingSegment:
    """One verified source-to-target interval in a liftover map."""

    mapping_id: str
    source_assembly: str
    source_chromosome: str
    source_start: int
    source_end: int
    target_assembly: str
    target_chromosome: str
    target_start: int
    target_end: int
    strand: str
    source_version: str

    def __post_init__(self) -> None:
        for name in (
            "mapping_id",
            "source_assembly",
            "source_chromosome",
            "target_assembly",
            "target_chromosome",
            "source_version",
        ):
            if not str(getattr(self, name)).strip():
                raise ValidationError(f"{name} must not be empty")
        if self.source_start < 1 or self.source_end < self.source_start:
            raise ValidationError("source mapping interval is invalid")
        if self.target_start < 1 or self.target_end < self.target_start:
            raise ValidationError("target mapping interval is invalid")
        if self.source_length != self.target_length:
            raise ValidationError("mapping segments must preserve interval length")
        if self.strand not in {"+", "-"}:
            raise ValidationError("mapping strand must be + or -")

    @property
    def source_length(self) -> int:
        return self.source_end - self.source_start + 1

    @property
    def target_length(self) -> int:
        return self.target_end - self.target_start + 1

    def contains(self, chromosome: str, start: int, end: int) -> bool:
        return (
            self.source_chromosome == chromosome
            and self.source_start <= start
            and end <= self.source_end
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ProjectionResult:
    """Mapped identity or explicit abstention with mapping provenance."""

    status: ProjectionStatus
    source_variant: VariantIdentity
    projected_variant: VariantIdentity | None
    mapping_id: str | None
    reason: str
    source_version: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class ReferenceRegistry:
    """Resolve aliases without conflating assemblies or species."""

    def __init__(self, assemblies: Iterable[ReferenceAssembly]) -> None:
        values = tuple(assemblies)
        self._assemblies = {assembly.assembly_id: assembly for assembly in values}
        if len(self._assemblies) != len(values):
            raise ValidationError("reference assembly IDs must be unique")
        aliases: dict[str, str] = {}
        for assembly in values:
            for alias in (assembly.assembly_id, assembly.canonical_name, *assembly.aliases):
                key = alias.lower()
                previous = aliases.get(key)
                if previous is not None and previous != assembly.assembly_id:
                    raise ValidationError(f"reference alias is ambiguous: {alias}")
                aliases[key] = assembly.assembly_id
        self._aliases = aliases

    def resolve(self, value: str) -> ReferenceAssembly:
        try:
            return self._assemblies[self._aliases[value.strip().lower()]]
        except KeyError as exc:
            raise ValidationError(f"unknown reference assembly: {value}") from exc

    def all(self) -> tuple[ReferenceAssembly, ...]:
        return tuple(self._assemblies.values())

    def manifest(self) -> dict[str, Any]:
        return {
            "registry_version": "references-2026.08",
            "assemblies": [assembly.to_dict() for assembly in self.all()],
            "content_address": content_hash(self.all()),
        }


def default_reference_registry() -> ReferenceRegistry:
    """Return the human-reference assemblies used by the public adapters."""

    return ReferenceRegistry(
        (
            ReferenceAssembly(
                assembly_id="GRCh38",
                canonical_name="GRCh38",
                species="Homo sapiens",
                release="GCA_000001405.15",
                aliases=("hg38", "GRCh38.p14"),
                source_ids=("SRC-UCSC-REST", "SRC-ENSEMBL-REST"),
                accession="GCA_000001405.15",
            ),
            ReferenceAssembly(
                assembly_id="GRCh37",
                canonical_name="GRCh37",
                species="Homo sapiens",
                release="GCA_000001405.1",
                aliases=("hg19", "GRCh37.p13"),
                source_ids=("SRC-UCSC-REST", "SRC-ENSEMBL-REST"),
                accession="GCA_000001405.1",
            ),
        )
    )


class MappingCatalog:
    """Explicit mapping segments indexed by source and target assembly."""

    def __init__(self, segments: Iterable[MappingSegment]) -> None:
        self._segments = tuple(segments)
        if len({segment.mapping_id for segment in self._segments}) != len(self._segments):
            raise ValidationError("mapping IDs must be unique")

    def for_pair(self, source_assembly: str, target_assembly: str) -> tuple[MappingSegment, ...]:
        return tuple(
            segment
            for segment in self._segments
            if segment.source_assembly == source_assembly
            and segment.target_assembly == target_assembly
        )

    def locate(
        self,
        source_assembly: str,
        chromosome: str,
        start: int,
        end: int,
        target_assembly: str,
    ) -> tuple[MappingSegment, ...]:
        return tuple(
            segment
            for segment in self.for_pair(source_assembly, target_assembly)
            if segment.contains(chromosome, start, end)
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "segments": [segment.to_dict() for segment in self._segments],
            "content_address": content_hash(self._segments),
        }


class ReferenceProjector:
    """Project variants through a supplied mapping catalog, never implicitly."""

    def __init__(self, registry: ReferenceRegistry, mappings: MappingCatalog | None = None) -> None:
        self.registry = registry
        self.mappings = mappings or MappingCatalog(())

    def project(self, variant: VariantIdentity, target_build: str) -> ProjectionResult:
        source = self.registry.resolve(variant.genome_build)
        target = self.registry.resolve(target_build)
        if source.species != target.species:
            return ProjectionResult(
                ProjectionStatus.ABSTAINED,
                variant,
                None,
                None,
                "source and target assemblies belong to different species",
            )
        if source.assembly_id == target.assembly_id:
            return ProjectionResult(
                ProjectionStatus.IDENTITY,
                variant,
                replace(
                    variant, annotations=dict(variant.annotations) | {"projection": "identity"}
                ),
                None,
                "source and target assemblies are identical",
                source.release,
            )
        if variant.kind == VariantKind.BREAKEND:
            return ProjectionResult(
                ProjectionStatus.ABSTAINED,
                variant,
                None,
                None,
                "breakend projection requires a graph-aware mate mapping",
            )
        segments = self.mappings.locate(
            source.assembly_id,
            variant.chromosome,
            variant.start,
            variant.end,
            target.assembly_id,
        )
        if not segments:
            return ProjectionResult(
                ProjectionStatus.ABSTAINED,
                variant,
                None,
                None,
                "no explicit mapping segment contains the full variant interval",
            )
        if len(segments) > 1:
            return ProjectionResult(
                ProjectionStatus.PARTIAL,
                variant,
                None,
                None,
                "multiple mapping segments overlap the variant interval",
            )
        segment = segments[0]
        start, end = self._project_interval(segment, variant.start, variant.end)
        reference, alternate = self._project_alleles(
            variant.reference, variant.alternate, segment.strand
        )
        projected = replace(
            variant,
            chromosome=segment.target_chromosome,
            start=start,
            end=end,
            reference=reference,
            alternate=alternate,
            genome_build=target.assembly_id,
            variant_id=f"{target.assembly_id}:{segment.target_chromosome}:{start}:{reference}>{alternate}",
            annotations=dict(variant.annotations)
            | {
                "projection": "mapped",
                "source_assembly": source.assembly_id,
                "target_assembly": target.assembly_id,
                "mapping_id": segment.mapping_id,
                "mapping_strand": segment.strand,
            },
        )
        return ProjectionResult(
            ProjectionStatus.MAPPED,
            variant,
            projected,
            segment.mapping_id,
            "variant interval mapped through one explicit segment",
            segment.source_version,
        )

    @staticmethod
    def _project_interval(segment: MappingSegment, start: int, end: int) -> tuple[int, int]:
        if segment.strand == "+":
            return (
                segment.target_start + (start - segment.source_start),
                segment.target_start + (end - segment.source_start),
            )
        return (
            segment.target_end - (end - segment.source_start),
            segment.target_end - (start - segment.source_start),
        )

    @staticmethod
    def _project_alleles(reference: str, alternate: str, strand: str) -> tuple[str, str]:
        if strand == "+":
            return reference, alternate
        return _reverse_complement(reference), _reverse_complement(alternate)


def _reverse_complement(sequence: str) -> str:
    complement = str.maketrans("ACGTNacgtn", "TGCANtgcan")
    return sequence.translate(complement)[::-1].upper()
