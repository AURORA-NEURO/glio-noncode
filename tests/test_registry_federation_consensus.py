"""Deep contract tests for quorum-safe federation consensus."""

# ruff: noqa: E501, I001

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package_registry as registry_model
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package_registry_federation as federation_model
from glio_noncode import registry_federation_consensus, registry_federation_consensus_audit, registry_federation_consensus_query
from glio_noncode.errors import ValidationError
from tests.test_assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package import DurableCatalogPromotionPackageFixture


class RegistryFederationConsensusTests(DurableCatalogPromotionPackageFixture):
    """Exercise safe selection and every public consensus projection."""

    def _registries(self, root: Path):
        ready_package = self.package_for(root / "ready-input", package_id="consensus-package")
        held_package = self.package_for(root / "held-input", package_id="consensus-package", held=True)
        ready = registry_model.build_registry((ready_package,), registry_id="consensus-ready")
        ready_copy = registry_model.build_registry((ready_package,), registry_id="consensus-copy")
        held = registry_model.build_registry((held_package,), registry_id="consensus-held")
        paths = (root / "ready", root / "copy", root / "held")
        for value, path in zip((ready, ready_copy, held), paths, strict=True):
            registry_model.write_registry(value, path)
        return paths

    def _receipt(self, root: Path, *peer_names: str, quorum: int | None = None):
        ready, copy, held = self._registries(root)
        paths = {"primary": ready, "replica": copy, "archive": held}
        peers = tuple((name, paths[name]) for name in peer_names)
        federation = federation_model.build_federation_from_directories(peers, federation_id="consensus-federation", quorum=quorum)
        return registry_federation_consensus.build_consensus(federation, consensus_id="consensus-receipt", quorum=quorum)

    def test_clean_replicas_select_one_address_and_accept(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self._receipt(Path(temporary), "primary", "replica")
            package = value.packages[0]
            self.assertEqual((value.state, value.decision, value.accepted), ("consistent", "accept", True))
            self.assertEqual((value.package_count, value.selected_count, value.unresolved_count, value.action_count), (1, 1, 0, 0))
            self.assertEqual((package.resolution, package.candidate_count, package.observed_peer_count), ("selected", 1, 2))
            self.assertTrue(package.selected_address)
            self.assertTrue(package.candidates[0].selected)
            self.assertEqual(package.candidates[0].support_count, 2)
            self.assertEqual(registry_federation_consensus.address_consensus(value), value.content_address)

    def test_divergent_replicas_refuse_selection_and_emit_blocking_actions(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self._receipt(Path(temporary), "primary", "archive")
            package = value.packages[0]
            self.assertEqual((value.state, value.decision, value.accepted), ("conflicted", "reject", False))
            self.assertEqual((package.resolution, package.candidate_count, package.selected_address), ("unresolved", 2, ""))
            self.assertEqual([candidate.selected for candidate in package.candidates], [False, False])
            self.assertEqual([action.kind for action in value.actions], ["inspect-divergence", "hold-package"])
            self.assertTrue(all(action.severity == "blocking" for action in value.actions))
            self.assertEqual(value.unresolved_count, 1)

    def test_three_peer_majority_selects_but_retains_dissent_for_review(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self._receipt(Path(temporary), "primary", "replica", "archive")
            package = value.packages[0]
            self.assertEqual(value.quorum, 2)
            self.assertEqual((value.state, value.decision, value.accepted), ("consistent", "review", False))
            self.assertEqual((package.resolution, package.candidate_count, package.selected_address != ""), ("selected", 2, True))
            self.assertEqual(max(candidate.support_count for candidate in package.candidates), 2)
            self.assertEqual(value.action_count, 1)
            self.assertEqual((value.actions[0].kind, value.actions[0].severity), ("inspect-divergence", "review"))

    def test_custom_quorum_can_hold_a_nonmajority_candidate(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self._receipt(Path(temporary), "primary", "replica", "archive", quorum=3)
            package = value.packages[0]
            self.assertEqual((value.quorum, package.resolution, package.candidate_count), (3, "unresolved", 2))
            self.assertEqual((value.state, value.decision), ("conflicted", "reject"))
            self.assertEqual(value.unresolved_count, 1)

    def test_mapping_json_and_four_file_disk_replay(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self._receipt(Path(temporary), "primary", "replica")
            self.assertEqual(registry_federation_consensus.consensus_from_mapping(value.to_dict()).to_dict(), value.to_dict())
            self.assertEqual(registry_federation_consensus.consensus_json(value), registry_federation_consensus.consensus_json(registry_federation_consensus.consensus_from_mapping(json.loads(registry_federation_consensus.consensus_json(value)))))
            destination = Path(temporary) / "consensus"
            registry_federation_consensus.write_consensus(value, destination)
            self.assertEqual(tuple(sorted(path.name for path in destination.iterdir())), tuple(sorted(registry_federation_consensus.FILES)))
            loaded = registry_federation_consensus.load_consensus(destination)
            self.assertEqual(loaded.to_dict(), value.to_dict())
            self.assertEqual(registry_federation_consensus.package_bytes(loaded), registry_federation_consensus.package_bytes(value))

    def test_independent_audit_passes_for_accepted_and_rejected_receipts(self):
        with tempfile.TemporaryDirectory() as temporary:
            clean = self._receipt(Path(temporary) / "clean", "primary", "replica")
            divergent = self._receipt(Path(temporary) / "divergent", "primary", "archive")
            for value in (clean, divergent):
                audit = registry_federation_consensus_audit.audit_consensus(value)
                self.assertEqual((audit.check_count, audit.passed_count, audit.failed_count, audit.accepted), (16, 16, 0, True))
                self.assertEqual(tuple(item.check_id for item in audit.checks), registry_federation_consensus.CHECK_IDS)
                self.assertEqual(registry_federation_consensus_audit.audit_from_mapping(audit.to_dict()).to_dict(), audit.to_dict())
                self.assertEqual(registry_federation_consensus_audit.address_audit(audit), audit.content_address)

    def test_query_projects_candidates_actions_and_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self._receipt(Path(temporary), "primary", "archive")
            result = registry_federation_consensus_query.query_consensus(value, resources=("packages", "candidates", "actions", "evidence"), limit=100)
            resources = {row.resource for row in result.rows}
            self.assertTrue({"packages", "candidates", "actions", "evidence"}.issubset(resources))
            self.assertLessEqual(result.matched_count, result.total_count)
            self.assertEqual(result.returned_count, len(result.rows))
            self.assertEqual(registry_federation_consensus_query.query_from_mapping(result.to_dict()).to_dict(), result.to_dict())
            self.assertIn("blocking", registry_federation_consensus_query.render_query_markdown(result))
            self.assertTrue(registry_federation_consensus_query.query_csv(result).startswith("ordinal,resource,row_id"))

    def test_query_filters_unresolved_and_paginates_deterministically(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self._receipt(Path(temporary), "primary", "archive")
            first = registry_federation_consensus_query.query_consensus(value, resources=("all",), resolution="unresolved", offset=0, limit=1)
            second = registry_federation_consensus_query.query_consensus(value, resources=("all",), resolution="unresolved", offset=1, limit=1)
            self.assertEqual(first.matched_count, 4)
            self.assertEqual((first.returned_count, first.next_offset, first.truncated), (1, 1, True))
            self.assertEqual((second.returned_count, second.next_offset, second.truncated), (1, 2, True))
            self.assertEqual(first.rows[0].resolution, "unresolved")
            self.assertNotEqual(first.content_address, second.content_address)

    def test_query_validation_and_receipt_corruption_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self._receipt(Path(temporary), "primary", "replica")
            with self.assertRaises(ValidationError):
                registry_federation_consensus_query.build_query(value, resolution="unknown")
            with self.assertRaises(ValidationError):
                registry_federation_consensus_query.build_query(value, limit=0)
            corrupted = value.to_dict()
            corrupted["selected_count"] = 0
            with self.assertRaises(ValidationError):
                registry_federation_consensus.consensus_from_mapping(corrupted)
            corrupted = value.to_dict()
            corrupted["packages"] = list(corrupted["packages"])
            corrupted["packages"][0] = dict(corrupted["packages"][0])
            corrupted["packages"][0]["content_address"] = value.packages[0].content_address + "-changed"
            with self.assertRaises(ValidationError):
                registry_federation_consensus.consensus_from_mapping(corrupted)

    def test_projection_schema_and_capability_contracts(self):
        self.assertEqual(registry_federation_consensus.capabilities()["files"], registry_federation_consensus.FILES)
        self.assertEqual(registry_federation_consensus.consensus_schema()["required"], list(registry_federation_consensus.RegistryFederationConsensus.FIELDS))
        self.assertEqual(registry_federation_consensus.package_schema()["required"], list(registry_federation_consensus.RegistryFederationConsensusPackage.FIELDS))
        self.assertEqual(registry_federation_consensus.candidate_schema()["required"], list(registry_federation_consensus.RegistryFederationConsensusCandidate.FIELDS))
        self.assertEqual(registry_federation_consensus.action_schema()["required"], list(registry_federation_consensus.RegistryFederationConsensusAction.FIELDS))
        self.assertEqual(registry_federation_consensus_query.query_schema()["required"], list(registry_federation_consensus_query.RegistryFederationConsensusQuery.FIELDS))
        self.assertEqual(registry_federation_consensus_query.row_schema()["required"], list(registry_federation_consensus_query.RegistryFederationConsensusQueryRow.FIELDS))
        self.assertEqual(registry_federation_consensus_query.result_schema()["required"], list(registry_federation_consensus_query.RegistryFederationConsensusQueryResult.FIELDS))


if __name__ == "__main__":
    unittest.main()
