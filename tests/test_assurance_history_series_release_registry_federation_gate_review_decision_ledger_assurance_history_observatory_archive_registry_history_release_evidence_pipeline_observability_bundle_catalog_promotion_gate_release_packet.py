"""Independent release-packet contracts for catalog promotion handoffs."""

# ruff: noqa: E501, I001

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog as catalog
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_diff as diff
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate as gate
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_audit as gate_audit
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet as packet
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_query as packet_query
from glio_noncode.errors import ValidationError
from tests.test_assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_report import RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportFixture


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionReleasePacketFixture(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportFixture):
    def build_values(self, root: Path):
        left, right, baseline, candidate = self.documents_for(root)
        change = diff.build_diff(left, right, diff_id="packet-diff")
        report = self.report_for(right)
        release_gate = gate.build_promotion_gate(change, report, gate_id="packet-gate")
        assurance = gate_audit.audit_gate(release_gate)
        return left, right, baseline, candidate, change, report, release_gate, assurance

    @staticmethod
    def report_for(value):
        from glio_noncode.assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_report import build_report

        return build_report(value, report_id="packet-report")


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionReleasePacketBuildTests(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionReleasePacketFixture):
    def test_ready_packet_is_a_complete_addressed_handoff(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, _, _, _, _, _, release_gate, assurance = self.build_values(Path(temporary))
            value = packet.build_release_packet(release_gate, assurance, packet_id="ready-packet")
            self.assertEqual(value.state, "ready")
            self.assertEqual(value.decision, "promote")
            self.assertTrue(value.accepted)
            self.assertTrue(value.release_ready)
            self.assertEqual((value.check_count, value.passed_count, value.failed_count), (27, 27, 0))
            self.assertEqual((value.blocking_failure_count, value.hold_failure_count, value.action_count), (0, 0, 0))
            self.assertEqual(value.failed_check_ids, ())
            self.assertEqual(packet.address_packet(value), value.content_address)
            self.assertEqual(packet.verify_packet(value).to_dict(), value.to_dict())

    def test_ready_packet_serializations_are_path_free_and_replayable(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, _, _, _, _, _, release_gate, assurance = self.build_values(Path(temporary))
            value = packet.build_release_packet(release_gate, assurance, packet_id="serialization-packet")
            encoded = packet.packet_json(value)
            self.assertNotIn(str(Path(temporary)), encoded)
            self.assertEqual(packet.packet_from_mapping(json.loads(encoded)).to_dict(), value.to_dict())
            self.assertIn("ordinal", packet.packet_csv(value).splitlines()[0])
            self.assertIn("No action required", packet.render_packet_markdown(value))
            for document in (value.to_dict(), value.summary(), packet.action_schema(), packet.packet_schema(), packet.capabilities()):
                self.assert_public(document)

    def test_held_packet_projects_every_failed_gate_check_as_an_action(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, right, _, _, change, report, _, _ = self.build_values(Path(temporary))
            held_policy = gate.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionPolicy(max_added=0)
            held_gate = gate.build_promotion_gate(change, report, policy=held_policy, gate_id="held-gate")
            held_assurance = gate_audit.audit_gate(held_gate)
            value = packet.build_release_packet(held_gate, held_assurance, packet_id="held-packet")
            self.assertEqual((value.state, value.decision, value.accepted, value.release_ready), ("held", "hold", True, False))
            self.assertEqual((value.check_count, value.passed_count, value.failed_count), (27, 26, 1))
            self.assertEqual((value.blocking_failure_count, value.hold_failure_count, value.action_count), (0, 1, 1))
            self.assertEqual(value.actions[0].source, "gate")
            self.assertEqual(value.actions[0].severity, "hold")
            self.assertEqual(value.actions[0].check_id, "added-budget")
            self.assertEqual(packet_query.query_packet(value, resource="actions").total_count, 1)
            self.assertEqual(packet_query.query_packet(value, resource="gate-actions").total_count, 1)
            self.assertEqual(packet_query.query_packet(value, resource="audit-actions").total_count, 0)
            self.assertEqual(packet_query.query_packet(value, resource="holds").total_count, 1)
            evidence = packet_query.query_packet(value, resource="evidence")
            self.assertEqual(evidence.returned_count, 1)
            self.assertIn("evidence_address", evidence.records[0])
            self.assertEqual(right.entry_count, 2)

    def test_blocked_packet_prioritizes_integrity_actions(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, right, _, _, _, report, _, _ = self.build_values(Path(temporary))
            empty = catalog.build_catalog_from_directories((), catalog_id="empty-catalog")
            blocked_change = diff.build_diff(empty, right, diff_id="blocked-diff")
            blocked_gate = gate.build_promotion_gate(blocked_change, report, gate_id="blocked-gate")
            blocked_assurance = gate_audit.audit_gate(blocked_gate)
            value = packet.build_release_packet(blocked_gate, blocked_assurance, packet_id="blocked-packet")
            self.assertEqual((value.state, value.decision, value.accepted, value.release_ready), ("blocked", "block", False, False))
            self.assertGreater(value.blocking_failure_count, 0)
            self.assertEqual(value.action_count, value.failed_count)
            self.assertEqual(packet_query.query_packet(value, resource="blocking").total_count, value.blocking_failure_count)
            self.assertEqual(packet_query.query_packet(value, resource="holds").total_count, 0)
            self.assertTrue(all(action.severity == "blocking" for action in value.actions))

    def test_packet_query_filters_and_pagination_are_deterministic(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, _, _, _, change, report, _, _ = self.build_values(Path(temporary))
            policy = gate.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionPolicy(max_added=0, max_ready_regression=0)
            release_gate = gate.build_promotion_gate(change, report, policy=policy, gate_id="query-gate")
            value = packet.build_release_packet(release_gate, gate_audit.audit_gate(release_gate), packet_id="query-packet")
            all_actions = packet_query.query_packet(value, resource="actions", limit=27)
            self.assertEqual(all_actions.total_count, 1)
            self.assertEqual(all_actions.returned_count, 1)
            self.assertEqual(packet_query.query_packet(value, source="audit").total_count, 0)
            self.assertEqual(packet_query.query_packet(value, resource="actions", source="gate", severity="hold").total_count, 1)
            self.assertEqual(packet_query.query_packet(value, resource="actions", text="ADDED-BUDGET").total_count, 1)
            self.assertEqual(packet_query.query_packet(value, offset=1).returned_count, 0)
            encoded = packet_query.query_json(all_actions)
            replayed = packet_query.query_result_from_mapping(json.loads(encoded))
            self.assertEqual(replayed.to_dict(), all_actions.to_dict())
            self.assertIn("Resource", packet_query.render_query_markdown(all_actions))
            self.assertIn("check_id", packet_query.query_csv(all_actions).splitlines()[0])

    def test_tamper_and_malformed_mappings_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, _, _, _, _, _, release_gate, assurance = self.build_values(Path(temporary))
            value = packet.build_release_packet(release_gate, assurance, packet_id="tamper-packet")
            tampered = value.to_dict()
            tampered["failed_count"] = 1
            with self.assertRaises(ValidationError):
                packet.packet_from_mapping(tampered)
            malformed = value.to_dict()
            malformed["actions"] = ("not-a-mapping",)
            with self.assertRaises(ValidationError):
                packet.packet_from_mapping(malformed)
            query = packet_query.query_packet(value, resource="actions")
            query_mapping = query.to_dict()
            query_mapping["returned_count"] = 1
            with self.assertRaises(ValidationError):
                packet_query.query_result_from_mapping(query_mapping)

    def test_action_addresses_and_failure_order_are_replayable(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, right, _, _, change, report, _, _ = self.build_values(Path(temporary))
            policy = gate.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionPolicy(max_added=0)
            release_gate = gate.build_promotion_gate(change, report, policy=policy, gate_id="ordered-gate")
            value = packet.build_release_packet(release_gate, gate_audit.audit_gate(release_gate), packet_id="ordered-packet")
            self.assertEqual(tuple(action.ordinal for action in value.actions), tuple(range(1, value.action_count + 1)))
            self.assertEqual(tuple(action.check_id for action in value.actions), value.failed_check_ids)
            for action in value.actions:
                self.assertEqual(packet.address_action(action), action.content_address)
                self.assertEqual(action.to_dict()["content_address"], action.content_address)
                self.assertTrue(action.evidence_address)
            self.assertEqual(packet.packet_from_mapping(value.to_dict()).actions[0].content_address, value.actions[0].content_address)
            self.assertEqual(right.entry_count, 2)

    def test_packet_query_mapping_and_resource_shapes_are_strict(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, _, _, _, _, _, release_gate, assurance = self.build_values(Path(temporary))
            value = packet.build_release_packet(release_gate, assurance, packet_id="shape-packet")
            for resource in packet_query.RESOURCES:
                page = packet_query.query_packet(value, resource=resource, limit=packet_query.DEFAULT_LIMIT)
                self.assertEqual(packet_query.verify_query(page).to_dict(), page.to_dict())
                self.assertEqual(packet_query.query_from_mapping(value.to_dict(), resource=resource).to_dict(), page.to_dict())
            query_mapping = {"resource": "actions", "source": None, "severity": None, "check_id": None, "text": None, "offset": 0, "limit": 5}
            query = packet_query.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketQuery.from_mapping(query_mapping)
            self.assertEqual(query.to_dict(), query_mapping)
            with self.assertRaises(ValidationError):
                packet_query.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketQuery.from_mapping({**query_mapping, "unknown": True})

    def test_packet_summary_is_compact_and_deterministic(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, _, _, _, _, _, release_gate, assurance = self.build_values(Path(temporary))
            value = packet.build_release_packet(release_gate, assurance, packet_id="summary-packet")
            summary = value.summary()
            self.assertNotIn("actions", summary)
            self.assertEqual(tuple(summary), tuple(field for field in packet.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacket.FIELDS if field != "actions"))
            self.assertEqual(json.loads(packet.packet_json(value))["packet_id"], "summary-packet")
            self.assertEqual(json.loads(packet_query.query_json(packet_query.query_packet(value)))["query"]["resource"], "summary")

    def test_action_schema_covers_public_action_fields(self):
        schema = packet.action_schema()
        properties = schema["properties"]
        self.assertEqual(schema["required"], list(packet.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleaseAction.FIELDS))
        self.assertEqual(schema["additionalProperties"], False)
        self.assertEqual(properties["ordinal"]["minimum"], 1)
        self.assertEqual(properties["ordinal"]["maximum"], packet.MAX_ACTIONS)
        self.assertEqual(properties["source"]["enum"], list(packet.SOURCES))
        self.assertTrue(properties["content_address"]["pattern"].startswith("^" + packet.ACTION_PREFIX))
        self.assertEqual(packet.packet_schema()["required"], list(packet.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacket.FIELDS))
        self.assertEqual(packet_query.query_result_schema()["properties"]["records"]["maxItems"], packet_query.MAX_QUERY_ITEMS)

    def test_capabilities_advertise_the_operator_contract(self):
        packet_capabilities = packet.capabilities()
        query_capabilities = packet_query.capabilities()
        self.assertEqual(packet_capabilities["packet_prefix"], packet.PACKET_PREFIX)
        self.assertEqual(packet_capabilities["action_prefix"], packet.ACTION_PREFIX)
        self.assertIn("gate and independent-audit composition", packet_capabilities["features"])
        self.assertIn("failure-to-action projection", packet_capabilities["features"])
        self.assertIn("JSON CSV and Markdown exports", packet_capabilities["features"])
        self.assertEqual(query_capabilities["query_prefix"], packet_query.QUERY_PREFIX)
        self.assertEqual(query_capabilities["resources"], packet_query.RESOURCES)
        self.assertEqual(query_capabilities["sources"], packet.SOURCES)
        self.assertIn("deterministic pagination", query_capabilities["features"])
        self.assertIn("content-addressed result replay", query_capabilities["features"])
        self.assertEqual(query_capabilities["limits"]["default_limit"], packet_query.DEFAULT_LIMIT)
        self.assertEqual(query_capabilities["limits"]["max_query_items"], packet_query.MAX_QUERY_ITEMS)
        self.assertEqual(query_capabilities["schemas"], ("query", "query-result"))
        self.assertEqual(packet_capabilities["schemas"], ("action", "packet"))
        self.assertEqual(packet_capabilities["states"], packet.STATES)
        self.assertEqual(packet_capabilities["decisions"], packet.DECISIONS)
        self.assertEqual(packet_capabilities["sources"], packet.SOURCES)
        self.assertEqual(packet_capabilities["limits"]["max_actions"], packet.MAX_ACTIONS)
        self.assertTrue(packet_capabilities["version"].endswith("release-packet-v1"))
        self.assertTrue(query_capabilities["version"].endswith("release-packet-v1-query-v1"))
        self.assertTrue(packet_capabilities["boundary"].startswith("public_"))
        self.assertTrue(query_capabilities["boundary"].startswith("public_"))

    def test_contract_constants_and_capability_limits_are_stable(self):
        self.assertEqual(packet.STATES, ("ready", "held", "blocked"))
        self.assertEqual(packet.DECISIONS, ("promote", "hold", "block"))
        self.assertEqual(packet.SOURCES, ("gate", "audit"))
        self.assertEqual(packet.MAX_ACTIONS, 27)
        self.assertEqual(packet_query.RESOURCES, ("summary", "actions", "gate-actions", "audit-actions", "blocking", "holds", "evidence"))
        self.assertEqual(packet_query.MAX_LIMIT, 27)
        self.assertEqual(packet_query.MAX_QUERY_ITEMS, 28)
        self.assertEqual(packet.capabilities()["limits"]["max_actions"], 27)
        self.assertEqual(packet_query.capabilities()["limits"]["max_limit"], 27)


if __name__ == "__main__":
    unittest.main()
