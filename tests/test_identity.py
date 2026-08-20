from __future__ import annotations

import unittest

from glio_noncode.errors import ValidationError
from glio_noncode.identity import interval_distance, normalize_chromosome, parse_variant
from glio_noncode.models import VariantKind


class IdentityTests(unittest.TestCase):
    def test_parse_snv_and_normalize_chromosome(self) -> None:
        variant = parse_variant("7:100:A>G")
        self.assertEqual(variant.chromosome, "chr7")
        self.assertEqual(variant.kind, VariantKind.SNV)
        self.assertEqual(variant.canonical_key, "GRCh38:chr7:100:100:A:G")

    def test_parse_indel(self) -> None:
        variant = parse_variant("chr2-100-AT-A", genome_build="GRCh37")
        self.assertEqual(variant.kind, VariantKind.INDEL)
        self.assertEqual(variant.end, 101)
        self.assertEqual(variant.genome_build, "GRCh37")

    def test_parse_breakend(self) -> None:
        variant = parse_variant("chr3:400:BND:chr8:900")
        self.assertEqual(variant.kind, VariantKind.BREAKEND)
        self.assertEqual(variant.annotations["mate"], "chr8:900")

    def test_invalid_variant_is_explicit(self) -> None:
        with self.assertRaises(ValidationError):
            parse_variant("not-a-variant")

    def test_interval_distance(self) -> None:
        self.assertEqual(interval_distance(("chr1", 10, 20), ("chr1", 30, 40)), 10)
        self.assertEqual(interval_distance(("chr1", 10, 20), ("chr1", 20, 25)), 0)
        self.assertIsNone(interval_distance(("chr1", 10, 20), ("chr2", 10, 20)))
        self.assertEqual(normalize_chromosome("CHR7"), "chr7")
