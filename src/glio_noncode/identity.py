"""Variation normalization for the supported input subset."""

from __future__ import annotations

import re
from dataclasses import replace
from typing import Any, Mapping

from .errors import ValidationError
from .models import VariantIdentity, VariantKind, VariantOrigin

_COMPACT = re.compile(
    r"^(?P<chrom>[^:]+):(?P<pos>[0-9]+):(?P<ref>[A-Za-z*-]+)>(?P<alt>[A-Za-z*-]+)$"
)
_DASHED = re.compile(
    r"^(?P<chrom>[^-]+)-(?P<pos>[0-9]+)-(?P<ref>[A-Za-z*-]+)-(?P<alt>[A-Za-z*-]+)$"
)
_BREAKEND = re.compile(r"^(?P<chrom>[^:]+):(?P<pos>[0-9]+):BND:(?P<mate>.+)$")


def normalize_chromosome(chromosome: str) -> str:
    """Normalize common chromosome spellings without changing contig identity."""

    normalized = chromosome.strip()
    if not normalized:
        raise ValidationError("chromosome must not be empty")
    if normalized.lower().startswith("chr"):
        normalized = normalized[3:]
    return f"chr{normalized}"


def normalize_allele(allele: str) -> str:
    """Normalize an allele for deterministic identity comparison."""

    normalized = allele.strip().upper()
    if not normalized or any(char not in "ACGTN*-" for char in normalized):
        raise ValidationError(f"invalid allele: {allele!r}")
    return normalized


def infer_kind(reference: str, alternate: str, *, breakend: bool = False) -> VariantKind:
    """Infer a bounded variation kind from normalized alleles."""

    if breakend:
        return VariantKind.BREAKEND
    if reference == "*" or alternate == "*":
        return VariantKind.CNV
    if len(reference) == 1 and len(alternate) == 1:
        return VariantKind.SNV
    return VariantKind.INDEL


def parse_variant(value: str, *, genome_build: str = "GRCh38", variant_id: str | None = None) -> VariantIdentity:
    """Parse a compact SNV/indel or bounded breakend notation."""

    text = value.strip()
    match = _COMPACT.match(text) or _DASHED.match(text)
    if match:
        groups = match.groupdict()
        chromosome = normalize_chromosome(groups["chrom"])
        position = int(groups["pos"])
        reference = normalize_allele(groups["ref"])
        alternate = normalize_allele(groups["alt"])
        kind = infer_kind(reference, alternate)
        canonical = f"{genome_build}:{chromosome}:{position}:{reference}>{alternate}"
        return VariantIdentity(
            variant_id=variant_id or canonical,
            kind=kind,
            chromosome=chromosome,
            start=position,
            end=position + max(len(reference), 1) - 1,
            reference=reference,
            alternate=alternate,
            genome_build=genome_build,
        )
    breakend = _BREAKEND.match(text)
    if breakend:
        groups = breakend.groupdict()
        chromosome = normalize_chromosome(groups["chrom"])
        position = int(groups["pos"])
        mate = groups["mate"].strip()
        if not mate:
            raise ValidationError("breakend mate must not be empty")
        canonical = f"{genome_build}:{chromosome}:{position}:BND:{mate}"
        return VariantIdentity(
            variant_id=variant_id or canonical,
            kind=VariantKind.BREAKEND,
            chromosome=chromosome,
            start=position,
            end=position,
            reference="N",
            alternate=f"BND[{mate}]",
            genome_build=genome_build,
            annotations={"mate": mate},
        )
    raise ValidationError(
        "variant must use CHROM:POS:REF>ALT, CHROM-POS-REF-ALT, or CHROM:POS:BND:MATE"
    )


def normalize_variant(raw: Mapping[str, Any], *, default_build: str = "GRCh38") -> VariantIdentity:
    """Normalize a mapping from an intake adapter into a typed identity."""

    if "notation" in raw:
        variant = parse_variant(
            str(raw["notation"]),
            genome_build=str(raw.get("genome_build", default_build)),
            variant_id=str(raw.get("variant_id")) if raw.get("variant_id") else None,
        )
        origin = VariantOrigin(str(raw.get("origin", VariantOrigin.UNCERTAIN.value)))
        return replace(
            variant,
            origin=origin,
            clonality=str(raw.get("clonality", "unknown")),
            sample_id=str(raw.get("sample_id", "unspecified")),
            annotations=dict(raw.get("annotations", {})),
        )
    return VariantIdentity.from_dict(raw)


def variant_interval(variant: VariantIdentity) -> tuple[str, int, int]:
    """Return a normalized interval tuple for overlap and indexing."""

    return variant.chromosome, variant.start, variant.end


def interval_distance(left: tuple[str, int, int], right: tuple[str, int, int]) -> int | None:
    """Return base distance for same-contig intervals, or None for different contigs."""

    if left[0] != right[0]:
        return None
    if left[2] < right[1]:
        return right[1] - left[2]
    if right[2] < left[1]:
        return left[1] - right[2]
    return 0
