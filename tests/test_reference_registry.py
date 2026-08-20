from __future__ import annotations

import unittest

from glio_noncode.identity import parse_variant
from glio_noncode.reference_registry import (
    CoordinateSystem,
    MappingCatalog,
    MappingSegment,
    ProjectionStatus,
    ReferenceProjector,
    default_reference_registry,
)


class ReferenceRegistryTests(unittest.TestCase):
    def test_default_registry_resolves_common_aliases(self) -> None:
        registry = default_reference_registry()
        self.assertEqual(registry.resolve("hg38").assembly_id, "GRCh38")
        self.assertEqual(registry.resolve("GRCh37.p13").assembly_id, "GRCh37")
        self.assertEqual(
            registry.resolve("hg38").coordinate_system, CoordinateSystem.ONE_BASED_INCLUSIVE
        )

    def test_forward_projection_preserves_alleles_and_records_mapping(self) -> None:
        variant = parse_variant("7:102:A>T", genome_build="GRCh38", variant_id="v1")
        mapping = MappingSegment(
            "map-1",
            "GRCh38",
            "chr7",
            100,
            109,
            "GRCh37",
            "chr7",
            200,
            209,
            "+",
            "chain-fixture-1",
        )
        result = ReferenceProjector(
            default_reference_registry(), MappingCatalog((mapping,))
        ).project(variant, "hg19")
        self.assertEqual(result.status, ProjectionStatus.MAPPED)
        assert result.projected_variant is not None
        self.assertEqual(result.projected_variant.start, 202)
        self.assertEqual(result.projected_variant.alternate, "T")
        self.assertEqual(result.mapping_id, "map-1")

    def test_reverse_projection_reverse_complements_alleles(self) -> None:
        variant = parse_variant("7:102:AC>GT", genome_build="GRCh38", variant_id="v2")
        mapping = MappingSegment(
            "map-reverse",
            "GRCh38",
            "chr7",
            100,
            109,
            "GRCh37",
            "chr7",
            1000,
            1009,
            "-",
            "chain-fixture-2",
        )
        result = ReferenceProjector(
            default_reference_registry(), MappingCatalog((mapping,))
        ).project(variant, "GRCh37")
        self.assertEqual(result.status, ProjectionStatus.MAPPED)
        assert result.projected_variant is not None
        self.assertEqual(
            (result.projected_variant.start, result.projected_variant.end), (1006, 1007)
        )
        self.assertEqual(
            (result.projected_variant.reference, result.projected_variant.alternate), ("GT", "AC")
        )

    def test_unmapped_partial_and_breakend_projections_abstain(self) -> None:
        projector = ReferenceProjector(default_reference_registry(), MappingCatalog(()))
        variant = parse_variant("7:102:A>T", genome_build="GRCh38")
        result = projector.project(variant, "GRCh37")
        self.assertEqual(result.status, ProjectionStatus.ABSTAINED)
        breakend = parse_variant("7:102:BND:8:200", genome_build="GRCh38")
        self.assertEqual(projector.project(breakend, "GRCh37").status, ProjectionStatus.ABSTAINED)

    def test_identity_projection_is_a_typed_result(self) -> None:
        variant = parse_variant("7:102:A>T", genome_build="GRCh38")
        result = ReferenceProjector(default_reference_registry()).project(variant, "hg38")
        self.assertEqual(result.status, ProjectionStatus.IDENTITY)
        self.assertEqual(result.projected_variant.annotations["projection"], "identity")


if __name__ == "__main__":
    unittest.main()
