from __future__ import annotations

import unittest

from glio_noncode.reference_alpha import (
    GeneAliasVersionResolver,
    LicenseUseRestrictionRegistry,
    PopulationFrequencyAdapter,
    ReferenceAlphaState,
    ReferenceSnapshotManager,
)


class ReferenceAlphaTests(unittest.TestCase):
    def test_gene_alias_resolves_version_and_alias(self) -> None:
        result = GeneAliasVersionResolver().resolve(
            [
                {"query_id": "q1", "query": "EGFR.2"},
                {"query_id": "q2", "query": "erb-b1"},
            ],
            [
                {
                    "gene_id": "EGFR",
                    "symbol": "EGFR",
                    "aliases": ["erb-b1"],
                    "version": "2",
                    "assembly": "GRCh38",
                    "source_version": "v1",
                }
            ],
            assembly="GRCh38",
        )
        self.assertEqual(result.state, ReferenceAlphaState.SUPPORTED)
        self.assertEqual(
            result.resolutions[0].matches[0].match_basis, ("versioned_gene_id", "version_exact")
        )
        self.assertEqual(result.resolutions[1].matches[0].match_basis, ("alias",))

    def test_gene_alias_versionless_query_remains_ambiguous(self) -> None:
        result = GeneAliasVersionResolver().resolve(
            [{"query": "EGFR"}],
            [
                {"gene_id": "EGFR", "symbol": "EGFR", "version": "1", "assembly": "GRCh38"},
                {"gene_id": "EGFR", "symbol": "EGFR", "version": "2", "assembly": "GRCh38"},
            ],
        )
        self.assertEqual(result.state, ReferenceAlphaState.AMBIGUOUS)
        self.assertEqual(len(result.resolutions[0].matches), 2)

    def test_population_adapter_derives_frequency_from_ac_an(self) -> None:
        result = PopulationFrequencyAdapter().adapt(
            [
                {
                    "variant_id": "v1",
                    "population": "EUR",
                    "ancestry": "NFE",
                    "AC": 2,
                    "AN": 100,
                    "nhomalt": 0,
                    "genome_build": "GRCh38",
                }
            ],
            genome_build="GRCh38",
        )
        self.assertEqual(result.state, ReferenceAlphaState.SUPPORTED)
        self.assertEqual(result.observations[0].allele_frequency, 0.02)
        self.assertEqual(result.summaries[0].mean_frequency, 0.02)

    def test_population_adapter_retains_build_mismatch_and_missing_frequency(self) -> None:
        result = PopulationFrequencyAdapter().adapt(
            [
                {"variant_id": "v1", "population": "EUR", "genome_build": "GRCh37"},
                {"variant_id": "v1", "population": "AFR", "genome_build": "GRCh38"},
            ],
            genome_build="GRCh38",
        )
        self.assertEqual(result.state, ReferenceAlphaState.PARTIAL)
        self.assertEqual(result.summaries[0].state, ReferenceAlphaState.PARTIAL)
        self.assertEqual(result.issues[0].code, "genome_build_mismatch")

    def test_reference_snapshot_build_and_compare_checksums(self) -> None:
        manager = ReferenceSnapshotManager()
        left = manager.build(
            [
                {"resource_id": "fasta", "kind": "fasta", "uri": "ref.fa", "checksum": "a" * 64},
                {
                    "resource_id": "dict",
                    "kind": "dictionary",
                    "uri": "ref.dict",
                    "checksum": "b" * 64,
                },
            ],
            snapshot_id="s1",
            assembly="GRCh38",
            source_id="local",
        )
        right = manager.build(
            [
                {"resource_id": "fasta", "kind": "fasta", "uri": "ref.fa", "checksum": "c" * 64},
                {
                    "resource_id": "dict",
                    "kind": "dictionary",
                    "uri": "ref.dict",
                    "checksum": "b" * 64,
                },
            ],
            snapshot_id="s2",
            assembly="GRCh38",
            source_id="local",
        )
        comparison = manager.compare(left, right)
        self.assertEqual(comparison.state, ReferenceAlphaState.PARTIAL)
        self.assertEqual(comparison.changed_resource_ids, ("fasta",))
        self.assertEqual(comparison.unchanged_resource_ids, ("dict",))

    def test_reference_snapshot_expected_hash_mismatch_is_contradictory(self) -> None:
        snapshot = ReferenceSnapshotManager().build(
            [{"resource_id": "fasta", "kind": "fasta", "uri": "ref.fa", "checksum": "a" * 64}],
            snapshot_id="s1",
            assembly="GRCh38",
            source_id="local",
            expected_manifest_hash="sha256:wrong",
        )
        self.assertEqual(snapshot.state, ReferenceAlphaState.CONTRADICTORY)
        self.assertEqual(snapshot.issues[0].code, "manifest_hash_mismatch")

    def test_license_registry_allows_research_with_attribution(self) -> None:
        result = LicenseUseRestrictionRegistry().evaluate(
            [{"resource_id": "ref"}],
            [
                {
                    "resource_id": "ref",
                    "license_id": "MIT",
                    "allowed_uses": ["research"],
                    "attribution": "cite source",
                    "redistribution_allowed": True,
                }
            ],
            requested_use="research",
        )
        self.assertEqual(result.state, ReferenceAlphaState.SUPPORTED)
        self.assertTrue(result.decisions[0].allowed)
        self.assertTrue(result.decisions[0].needs_attribution)

    def test_license_registry_blocks_missing_and_conflicting_permissions(self) -> None:
        result = LicenseUseRestrictionRegistry().evaluate(
            [{"resource_id": "missing"}, {"resource_id": "conflict"}],
            [
                {
                    "resource_id": "conflict",
                    "license_id": "A",
                    "allowed_uses": ["research"],
                    "redistribution_allowed": True,
                },
                {
                    "resource_id": "conflict",
                    "license_id": "B",
                    "allowed_uses": ["commercial"],
                    "redistribution_allowed": False,
                },
            ],
            requested_use="research",
        )
        self.assertEqual(result.state, ReferenceAlphaState.CONTRADICTORY)
        self.assertIn("missing", result.missing_resource_ids)
        self.assertEqual(
            {item.state for item in result.decisions},
            {ReferenceAlphaState.ABSTAINED, ReferenceAlphaState.CONTRADICTORY},
        )


if __name__ == "__main__":
    unittest.main()
