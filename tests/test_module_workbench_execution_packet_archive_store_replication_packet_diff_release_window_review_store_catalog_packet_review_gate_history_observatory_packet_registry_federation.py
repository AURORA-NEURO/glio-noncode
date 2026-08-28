# ruff: noqa: E501

from __future__ import annotations

import json
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

import glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history as history
import glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet as packet
import glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry as registry
import glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation as federation
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.serialization import canonical_bytes
from tests.test_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry import (
    RegistryFixture,
)


class FederationFixture(RegistryFixture):
    def build_named_registry(
        self,
        registry_id: str,
        packet_ids: tuple[str, ...] = ("packet:a", "packet:b"),
    ):
        return registry.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
            tuple(self.closure_packet(packet_id) for packet_id in packet_ids),
            registry_id=registry_id,
        )

    def build_held_registry(self, registry_id: str = "registry:held"):
        ready = self.closure_packet(f"{registry_id}:ready")
        held = packet.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet(
            self.build(("hold", "hold")),
            policy=packet.default_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime_policy(
                policy_id=f"{registry_id}:policy",
                require_latest_release_ready=False,
            ),
            packet_id=f"{registry_id}:held",
        )
        return registry.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
            (ready, held), registry_id=registry_id
        )

    def build_blocked_registry(self, registry_id: str = "registry:blocked"):
        ready = self.closure_packet(f"{registry_id}:ready")
        blocked = packet.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet(
            self.build(("promote", "hold")), packet_id=f"{registry_id}:blocked"
        )
        return registry.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
            (ready, blocked), registry_id=registry_id
        )

    def build_federation(
        self,
        registry_ids: tuple[str, ...] = ("registry:a", "registry:b"),
    ):
        return federation.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(
            tuple(self.build_named_registry(registry_id) for registry_id in registry_ids),
            federation_id="federation:fixture",
        )

    @staticmethod
    def write_federation(value, destination, **kwargs):
        return federation.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(
            value, destination, **kwargs
        )


class FederationCoreTests(FederationFixture):
    def test_ready_federation_conserves_registries_and_packets(self):
        value = self.build_federation()
        self.assertTrue(value.accepted)
        self.assertTrue(value.release_ready)
        self.assertEqual(value.state, "ready")
        self.assertEqual(value.registry_count, 2)
        self.assertEqual(value.total_packet_count, 4)
        self.assertEqual(value.ready_registry_count, 2)
        self.assertEqual(value.held_registry_count, 0)
        self.assertEqual(value.blocked_registry_count, 0)
        self.assertEqual(value.accepted_registry_count, 2)
        self.assertEqual(value.release_ready_registry_count, 2)
        self.assertEqual(value.ready_packet_count, 4)
        self.assertEqual(value.held_packet_count, 0)
        self.assertEqual(value.blocked_packet_count, 0)
        self.assertEqual(value.accepted_packet_count, 4)
        self.assertEqual(value.release_ready_packet_count, 4)
        self.assertEqual([entry.ordinal for entry in value.entries], [0, 1])
        self.assertEqual([entry.registry_id for entry in value.entries], ["registry:a", "registry:b"])

    def test_federation_input_order_is_not_semantic(self):
        first = self.build_federation(("registry:b", "registry:a"))
        second = self.build_federation(("registry:a", "registry:b"))
        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(
            [entry.content_address for entry in first.entries],
            [entry.content_address for entry in second.entries],
        )
        self.assertEqual(
            [entry.ordinal for entry in first.entries],
            [entry.ordinal for entry in second.entries],
        )

    def test_federation_address_recomputes_without_receipt_addresses(self):
        value = self.build_federation()
        self.assertEqual(
            federation.address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(
                value
            ),
            value.content_address,
        )
        self.assertTrue(value.verification_address.startswith("module-workbench"))
        self.assertTrue(value.runtime_address.startswith("module-workbench"))

    def test_federation_verification_has_twenty_independent_checks(self):
        value = self.build_federation()
        receipt = federation.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(
            value
        )
        self.assertTrue(receipt.accepted)
        self.assertEqual(receipt.check_count, 20)
        self.assertEqual(receipt.failed_count, 0)
        self.assertEqual([check.ordinal for check in receipt.checks], list(range(20)))
        self.assertEqual(
            [check.kind for check in receipt.checks],
            [
                "federation-address",
                "entry-count",
                "entry-order",
                "registry-id-uniqueness",
                "registry-address-uniqueness",
                "registry-state-conservation",
                "registry-acceptance-conservation",
                "registry-readiness-conservation",
                "total-packet-count",
                "ready-packet-count",
                "held-packet-count",
                "blocked-packet-count",
                "accepted-packet-count",
                "release-ready-packet-count",
                "state-projection",
                "release-projection",
                "policy-link",
                "entry-addresses",
                "registry-links",
                "public-boundary",
            ],
        )

    def test_federation_runtime_has_five_stages_and_eight_policy_checks(self):
        value = self.build_federation()
        runtime = value.runtime
        self.assertIsNotNone(runtime)
        self.assertEqual(runtime.state, "ready")
        self.assertTrue(runtime.accepted)
        self.assertTrue(runtime.release_ready)
        self.assertEqual(runtime.stage_count, 5)
        self.assertEqual([stage.name for stage in runtime.stages], ["load", "verify", "policy", "project", "complete"])
        self.assertEqual(runtime.policy_check_count, 8)
        self.assertEqual(runtime.policy_failed_count, 0)
        self.assertEqual([check.ordinal for check in runtime.policy_checks], list(range(8)))

    def test_runtime_replay_is_addressed_and_repeatable(self):
        value = self.build_federation()
        replay = federation.run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_runtime(
            value, policy=value.policy, verification=value.verification
        )
        self.assertEqual(replay.to_dict(), value.runtime.to_dict())
        self.assertEqual(
            federation.address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_runtime(
                replay
            ),
            replay.content_address,
        )
        runtime_receipt = federation.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_runtime(
            replay, value, policy=value.policy, verification=value.verification
        )
        self.assertTrue(runtime_receipt.accepted)
        self.assertEqual(runtime_receipt.check_count, 6)

    def test_held_federation_preserves_accepted_nonready_registry(self):
        policy = federation.default_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_policy(
            policy_id="policy:held-federation",
            require_all_release_ready=False,
        )
        value = federation.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(
            (self.build_named_registry("registry:ready"), self.build_held_registry()),
            federation_id="federation:held",
            policy=policy,
        )
        self.assertTrue(value.accepted)
        self.assertFalse(value.release_ready)
        self.assertEqual(value.state, "held")
        self.assertEqual(value.ready_registry_count, 1)
        self.assertEqual(value.held_registry_count, 1)
        self.assertEqual(value.blocked_registry_count, 0)
        self.assertEqual(value.runtime.state, "held")
        self.assertTrue(value.runtime.accepted)
        self.assertFalse(value.runtime.release_ready)
        self.assertEqual(value.runtime.policy_failed_count, 0)
        self.assertEqual(value.runtime.policy_checks[6].kind, "release-ready-registries")
        self.assertTrue(value.runtime.policy_checks[6].passed)

    def test_blocked_federation_preserves_blocked_registry(self):
        value = federation.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(
            (self.build_named_registry("registry:ready"), self.build_blocked_registry()),
            federation_id="federation:blocked",
        )
        self.assertTrue(value.accepted)
        self.assertFalse(value.release_ready)
        self.assertEqual(value.state, "blocked")
        self.assertEqual(value.blocked_registry_count, 1)
        self.assertEqual(value.blocked_packet_count, 1)
        self.assertEqual(value.runtime.state, "blocked")
        self.assertFalse(value.runtime.accepted)
        self.assertFalse(value.runtime.release_ready)
        self.assertGreater(value.runtime.policy_failed_count, 0)
        self.assertEqual(value.runtime.stages[2].state, "blocked")

    def test_empty_federation_is_explicit_and_policy_governed(self):
        policy = federation.default_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_policy(
            policy_id="policy:empty",
            minimum_registries=0,
            allow_empty=True,
        )
        value = federation.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(
            (), federation_id="federation:empty", policy=policy
        )
        self.assertTrue(value.accepted)
        self.assertFalse(value.release_ready)
        self.assertEqual(value.state, "empty")
        self.assertEqual(value.registry_count, 0)
        self.assertEqual(value.total_packet_count, 0)
        self.assertEqual(value.runtime.state, "held")
        self.assertTrue(value.runtime.accepted)
        self.assertTrue(value.runtime.policy_checks[0].passed)
        self.assertTrue(value.runtime.policy_checks[-1].passed)

    def test_empty_federation_fails_without_empty_policy(self):
        value = federation.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(
            (), federation_id="federation:empty-default"
        )
        self.assertEqual(value.state, "empty")
        self.assertFalse(value.runtime.accepted)
        self.assertEqual(value.runtime.state, "blocked")
        self.assertEqual(value.runtime.policy_checks[0].kind, "minimum-registries")
        self.assertFalse(value.runtime.policy_checks[0].passed)
        self.assertFalse(value.runtime.policy_checks[-1].passed)

    def test_policy_packet_budget_can_hold_a_structurally_valid_federation(self):
        policy = federation.default_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_policy(
            policy_id="policy:packets",
            maximum_packets=3,
        )
        value = federation.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(
            (self.build_named_registry("registry:a"), self.build_named_registry("registry:b")),
            federation_id="federation:packet-budget",
            policy=policy,
        )
        self.assertTrue(value.accepted)
        self.assertEqual(value.total_packet_count, 4)
        self.assertFalse(value.runtime.accepted)
        failed = [check.kind for check in value.runtime.policy_checks if not check.passed]
        self.assertEqual(failed, ["maximum-packets"])

    def test_registry_budget_policy_can_block_a_federation(self):
        policy = federation.default_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_policy(
            policy_id="policy:registries",
            maximum_registries=1,
        )
        value = federation.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(
            (self.build_named_registry("registry:a"), self.build_named_registry("registry:b")),
            federation_id="federation:registry-budget",
            policy=policy,
        )
        self.assertEqual(value.registry_count, 2)
        self.assertFalse(value.runtime.accepted)
        self.assertIn("maximum-registries", [check.kind for check in value.runtime.policy_checks if not check.passed])

    def test_held_budget_policy_can_block_held_evidence(self):
        policy = federation.default_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_policy(
            policy_id="policy:no-held",
            maximum_held_registries=0,
            require_all_release_ready=False,
        )
        value = federation.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(
            (self.build_held_registry(),), federation_id="federation:no-held", policy=policy
        )
        self.assertEqual(value.state, "held")
        self.assertFalse(value.runtime.accepted)
        self.assertEqual(value.runtime.policy_checks[4].kind, "held-registry-budget")
        self.assertFalse(value.runtime.policy_checks[4].passed)

    def test_policy_mapping_round_trip(self):
        policy = federation.default_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_policy(
            policy_id="policy:roundtrip",
            minimum_registries=0,
            maximum_registries=12,
            maximum_packets=123,
            maximum_blocked_registries=2,
            maximum_held_registries=3,
            require_all_registries_accepted=False,
            require_all_release_ready=False,
            allow_empty=True,
        )
        restored = federation.federation_policy_from_mapping(policy.to_dict())
        self.assertEqual(restored.to_dict(), policy.to_dict())
        self.assertEqual(restored.content_address, policy.content_address)

    def test_entry_check_verification_stage_and_runtime_mapping_round_trips(self):
        value = self.build_federation()
        entry = federation.federation_entry_from_mapping(value.entries[0].to_dict())
        self.assertEqual(entry.to_dict(), value.entries[0].to_dict())
        check = federation.federation_check_from_mapping(value.verification.checks[0].to_dict())
        self.assertEqual(check.to_dict(), value.verification.checks[0].to_dict())
        verification = federation.federation_verification_from_mapping(value.verification.to_dict())
        self.assertEqual(verification.to_dict(), value.verification.to_dict())
        stage = federation.federation_stage_from_mapping(value.runtime.stages[0].to_dict())
        self.assertEqual(stage.to_dict(), value.runtime.stages[0].to_dict())
        runtime = federation.federation_runtime_from_mapping(value.runtime.to_dict())
        self.assertEqual(runtime.to_dict(), value.runtime.to_dict())
        restored = federation.federation_from_mapping(value.to_dict())
        self.assertEqual(restored.to_dict(), value.to_dict())

    def test_mapping_converters_reject_nonobjects(self):
        converters = (
            federation.federation_policy_from_mapping,
            federation.federation_entry_from_mapping,
            federation.federation_check_from_mapping,
            federation.federation_verification_from_mapping,
            federation.federation_stage_from_mapping,
            federation.federation_runtime_from_mapping,
            federation.federation_from_mapping,
        )
        for converter in converters:
            with self.subTest(converter=converter.__name__):
                with self.assertRaises(ValidationError):
                    converter([])

    def test_public_boundary_rejects_forbidden_policy_keys(self):
        value = self.build_federation()
        projection = value.to_dict()
        projection["agent"] = "not-public"
        with self.assertRaises(ValidationError):
            federation.federation_from_mapping(projection)


class FederationQueryTests(FederationFixture):
    def setUp(self):
        self.value = self.build_federation()

    def query(self, resource: str, **kwargs):
        return federation.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(
            self.value, resource=resource, **kwargs
        )

    def test_every_query_resource_has_conserved_total(self):
        expected = {
            "summary": 1,
            "registries": 2,
            "packet-rollup": 2,
            "verification": 1,
            "policy-checks": 8,
            "stages": 5,
        }
        for resource, total in expected.items():
            with self.subTest(resource=resource):
                result = self.query(resource)
                self.assertEqual(result.total, total)
                self.assertEqual(len(result.items), total)
                self.assertTrue(
                    federation.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_query(
                        result
                    )
                )

    def test_registry_query_has_state_acceptance_and_readiness_filters(self):
        result = self.query("registries", state="ready", accepted=True, release_ready=True)
        self.assertEqual(result.total, 2)
        self.assertEqual([item["registry_id"] for item in result.items], ["registry:a", "registry:b"])
        self.assertTrue(all(item["state"] == "ready" for item in result.items))

    def test_packet_rollup_query_preserves_each_registry_totals(self):
        result = self.query("packet-rollup")
        self.assertEqual(result.total, 2)
        self.assertEqual([item["registry_id"] for item in result.items], ["registry:a", "registry:b"])
        self.assertEqual([item["packet_count"] for item in result.items], [2, 2])
        self.assertTrue(all(item["rollup_kind"] == "registry-packets" for item in result.items))

    def test_verification_and_policy_queries_are_bounded(self):
        verification = self.query("verification")
        self.assertEqual(verification.total, 1)
        self.assertTrue(verification.items[0]["accepted"])
        checks = self.query("policy-checks")
        self.assertEqual(checks.total, 8)
        self.assertEqual(checks.items[0]["kind"], "minimum-registries")
        self.assertEqual(checks.items[-1]["kind"], "empty-federation")
        stages = self.query("stages")
        self.assertEqual(stages.total, 5)
        self.assertEqual(stages.items[-1]["name"], "complete")

    def test_text_filter_and_pagination_are_deterministic(self):
        result = self.query("registries", text="registry:b", offset=0, limit=1)
        self.assertEqual(result.total, 1)
        self.assertEqual(len(result.items), 1)
        self.assertEqual(result.items[0]["registry_id"], "registry:b")
        self.assertEqual(result.offset, 0)
        self.assertEqual(result.limit, 1)
        page = self.query("registries", offset=1, limit=1)
        self.assertEqual(page.total, 2)
        self.assertEqual(len(page.items), 1)
        self.assertEqual(page.items[0]["registry_id"], "registry:b")

    def test_empty_page_keeps_filtered_total(self):
        result = self.query("registries", offset=2, limit=5)
        self.assertEqual(result.total, 2)
        self.assertEqual(result.items, ())

    def test_query_filters_can_select_held_and_blocked_federations(self):
        held = federation.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(
            (self.build_held_registry(),), federation_id="federation:held-query"
        )
        result = federation.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(
            held, resource="summary", state="held", accepted=True, release_ready=False
        )
        self.assertEqual(result.total, 1)
        self.assertEqual(result.items[0]["state"], "held")
        blocked = federation.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(
            (self.build_blocked_registry(),), federation_id="federation:blocked-query"
        )
        result = federation.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(
            blocked, resource="summary", state="blocked", accepted=True, release_ready=False
        )
        self.assertEqual(result.total, 1)
        self.assertEqual(result.items[0]["state"], "blocked")

    def test_invalid_query_resource_state_and_bounds_are_rejected(self):
        with self.assertRaises(ValidationError):
            self.query("unknown")
        with self.assertRaises(ValidationError):
            self.query("registries", state="unknown")
        with self.assertRaises(ValidationError):
            self.query("registries", offset=-1)
        with self.assertRaises(ValidationError):
            self.query("registries", limit=0)
        with self.assertRaises(ValidationError):
            self.query("registries", limit=5000)
        with self.assertRaises(ValidationError):
            self.query("registries", text="x" * 5000)

    def test_query_exports_round_trip_to_json_and_have_tabular_markers(self):
        result = self.query("registries")
        encoded = federation.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_query_json(result)
        self.assertEqual(json.loads(encoded), result.to_dict())
        csv_text = federation.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_query_csv(result)
        self.assertIn("registry_id", csv_text)
        self.assertIn("registry:a", csv_text)
        markdown = federation.render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_query_markdown(result)
        self.assertIn("# Observatory Packet Registry Federation Query", markdown)
        self.assertIn("registry:b", markdown)

    def test_federation_exports_are_stable(self):
        encoded = federation.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_json(self.value)
        self.assertEqual(json.loads(encoded), self.value.to_dict())
        csv_text = federation.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_csv(self.value)
        self.assertIn("registry_id", csv_text)
        self.assertIn("registry_address", csv_text)
        markdown = federation.render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_markdown(self.value)
        self.assertIn("# Observatory Packet Registry Federation", markdown)
        self.assertIn("federation:fixture", markdown)

    def test_query_address_is_reproducible(self):
        first = self.query("packet-rollup")
        second = self.query("packet-rollup")
        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual(first.content_address, second.content_address)

    def test_query_json_does_not_leak_source_directory_text(self):
        result = self.query("summary")
        text = json.dumps(result.to_dict()).casefold()
        self.assertNotIn("directory", text)
        self.assertNotIn("path", text)
        self.assertNotIn("agent", text)
        self.assertNotIn("language", text)


class FederationPersistenceTests(FederationFixture):
    def test_exact_six_file_round_trip(self):
        value = self.build_federation()
        with tempfile.TemporaryDirectory() as root:
            destination = self.write_federation(value, Path(root) / "federation")
            self.assertEqual(
                {item.name for item in destination.iterdir()},
                {
                    "manifest.json",
                    "federation.json",
                    "registries.json",
                    "policy.json",
                    "verification.json",
                    "runtime.json",
                },
            )
            loaded = federation.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(destination)
            self.assertEqual(loaded.to_dict(), value.to_dict())
            self.assertEqual(loaded.content_address, value.content_address)
            self.assertTrue(loaded.verification.accepted)
            self.assertEqual(loaded.runtime.to_dict(), value.runtime.to_dict())

    def test_loaded_federation_can_be_verified_offline(self):
        value = self.build_federation()
        with tempfile.TemporaryDirectory() as root:
            destination = self.write_federation(value, Path(root) / "federation")
            loaded = federation.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(destination)
            verification = federation.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(loaded)
            self.assertTrue(verification.accepted)
            self.assertEqual(verification.check_count, 20)
            runtime = federation.run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_runtime(
                loaded, policy=loaded.policy, verification=loaded.verification
            )
            self.assertEqual(runtime.to_dict(), value.runtime.to_dict())

    def test_overwrite_requires_explicit_flag(self):
        value = self.build_federation()
        with tempfile.TemporaryDirectory() as root:
            destination = self.write_federation(value, Path(root) / "federation")
            with self.assertRaises(ValidationError):
                self.write_federation(value, destination)
            overwritten = federation.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(
                value, destination, overwrite=True
            )
            self.assertEqual(overwritten, destination)
            self.assertTrue(federation.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(destination).verification.accepted)

    def test_extra_file_is_rejected(self):
        value = self.build_federation()
        with tempfile.TemporaryDirectory() as root:
            destination = self.write_federation(value, Path(root) / "federation")
            (destination / "extra.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(ValidationError):
                federation.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(destination)

    def test_missing_file_is_rejected(self):
        value = self.build_federation()
        with tempfile.TemporaryDirectory() as root:
            destination = self.write_federation(value, Path(root) / "federation")
            (destination / "runtime.json").unlink()
            with self.assertRaises(ValidationError):
                federation.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(destination)

    def test_noncanonical_document_is_rejected(self):
        value = self.build_federation()
        with tempfile.TemporaryDirectory() as root:
            destination = self.write_federation(value, Path(root) / "federation")
            (destination / "federation.json").write_bytes(b'{ "wrong": true }\n')
            with self.assertRaises(ValidationError):
                federation.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(destination)

    def test_manifest_address_tamper_is_rejected(self):
        value = self.build_federation()
        with tempfile.TemporaryDirectory() as root:
            destination = self.write_federation(value, Path(root) / "federation")
            path = destination / "manifest.json"
            document = json.loads(path.read_text(encoding="utf-8"))
            document["manifest_address"] = "tampered:manifest"
            path.write_bytes(canonical_bytes(document))
            with self.assertRaises(ValidationError):
                federation.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(destination)

    def test_manifest_receipt_tamper_is_rejected(self):
        value = self.build_federation()
        with tempfile.TemporaryDirectory() as root:
            destination = self.write_federation(value, Path(root) / "federation")
            path = destination / "manifest.json"
            document = json.loads(path.read_text(encoding="utf-8"))
            document["artifact_files"][0]["byte_count"] += 1
            document["manifest_address"] = federation.content_hash(
                document | {"manifest_address": None},
                prefix=federation.MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_PREFIX + "-manifest",
            )
            path.write_bytes(canonical_bytes(document))
            with self.assertRaises(ValidationError):
                federation.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(destination)

    def test_each_payload_document_tamper_is_rejected(self):
        changes = {
            "federation.json": ("federation_id", "tampered:federation"),
            "registries.json": ("registry_count", 99),
            "policy.json": ("policy_id", "tampered:policy"),
            "verification.json": ("federation_address", "tampered:federation"),
            "runtime.json": ("runtime_id", "tampered:runtime"),
        }
        for file_name, (key, replacement) in changes.items():
            with self.subTest(file_name=file_name):
                value = self.build_federation()
                with tempfile.TemporaryDirectory() as root:
                    destination = self.write_federation(value, Path(root) / "federation")
                    path = destination / file_name
                    document = json.loads(path.read_text(encoding="utf-8"))
                    document[key] = replacement
                    path.write_bytes(canonical_bytes(document))
                    with self.assertRaises(ValidationError):
                        federation.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(destination)

    def test_every_manifest_file_byte_receipt_is_verified(self):
        value = self.build_federation()
        with tempfile.TemporaryDirectory() as root:
            destination = self.write_federation(value, Path(root) / "federation")
            path = destination / "manifest.json"
            document = json.loads(path.read_text(encoding="utf-8"))
            document["artifact_files"][1]["byte_address"] = "tampered:bytes"
            path.write_bytes(canonical_bytes(document))
            with self.assertRaises(ValidationError):
                federation.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(destination)

    def test_file_and_directory_symlinks_are_rejected(self):
        value = self.build_federation()
        with tempfile.TemporaryDirectory() as root:
            destination = self.write_federation(value, Path(root) / "federation")
            with self.assertRaises(ValidationError):
                federation.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(destination / "federation.json")
            try:
                link = Path(root) / "link"
                link.symlink_to(destination, target_is_directory=True)
            except (OSError, NotImplementedError):
                return
            with self.assertRaises(ValidationError):
                federation.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(link)

    def test_symlinked_payload_file_is_rejected(self):
        value = self.build_federation()
        with tempfile.TemporaryDirectory() as root:
            destination = self.write_federation(value, Path(root) / "federation")
            source = destination / "policy.json"
            replacement = Path(root) / "policy-copy.json"
            replacement.write_bytes(source.read_bytes())
            source.unlink()
            try:
                source.symlink_to(replacement)
            except (OSError, NotImplementedError):
                return
            with self.assertRaises(ValidationError):
                federation.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(destination)

    def test_mutated_federation_receipt_cannot_be_written(self):
        value = self.build_federation()
        value.content_address = "stale:federation"
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValidationError):
                self.write_federation(value, Path(root) / "federation")

    def test_mutated_entry_receipt_cannot_be_written(self):
        value = self.build_federation()
        value.entries[0].content_address = "stale:entry"
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValidationError):
                self.write_federation(value, Path(root) / "federation")

    def test_directory_builder_loads_two_registry_handoffs(self):
        with tempfile.TemporaryDirectory() as root:
            first = registry.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
                self.build_named_registry("registry:directory-a", ("packet:directory-a",)),
                Path(root) / "registry-a",
            )
            second = registry.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
                self.build_named_registry("registry:directory-b", ("packet:directory-b",)),
                Path(root) / "registry-b",
            )
            value = federation.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_from_directories(
                (second, first), federation_id="federation:directories"
            )
            self.assertEqual(value.registry_count, 2)
            self.assertEqual(value.total_packet_count, 2)
            self.assertEqual([entry.registry_id for entry in value.entries], ["registry:directory-a", "registry:directory-b"])


class FederationValidationTests(FederationFixture):
    def test_duplicate_registry_ids_are_rejected(self):
        first = self.build_named_registry("registry:duplicate", ("packet:first",))
        second = self.build_named_registry("registry:duplicate", ("packet:second",))
        with self.assertRaises(ValidationError):
            federation.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(
                (first, second)
            )

    def test_duplicate_registry_addresses_are_rejected(self):
        value = self.build_named_registry("registry:same", ("packet:same",))
        with self.assertRaises(ValidationError):
            federation.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(
                (value, value)
            )

    def test_untyped_registry_is_rejected(self):
        with self.assertRaises(ValidationError):
            federation.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(
                (object(),)
            )

    def test_unaccepted_registry_is_rejected(self):
        value = self.build_named_registry("registry:mutated", ("packet:mutated",))
        value.content_address = "tampered:registry"
        with self.assertRaises(ValidationError):
            federation.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(
                (value,)
            )

    def test_registry_count_bound_is_enforced(self):
        registries = tuple(
            self.build_named_registry(f"registry:{index}", (f"packet:{index}",))
            for index in range(65)
        )
        with self.assertRaises(ValidationError):
            federation.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(
                registries
            )

    def test_policy_bounds_are_validated(self):
        with self.assertRaises(ValidationError):
            federation.default_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_policy(
                policy_id="policy:invalid", minimum_registries=4, maximum_registries=3
            )
        with self.assertRaises(ValidationError):
            federation.default_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_policy(
                policy_id="policy:invalid", maximum_packets=0
            )
        with self.assertRaises(ValidationError):
            federation.default_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_policy(
                policy_id="policy:invalid", allow_empty="yes"
            )

    def test_federation_constructor_rejects_stale_entry_address(self):
        value = self.build_federation()
        mapping = value.to_dict()
        mapping["entries"][0]["content_address"] = "stale:entry"
        with self.assertRaises(ValidationError):
            federation.federation_from_mapping(mapping)

    def test_federation_constructor_rejects_state_count_drift(self):
        value = self.build_federation()
        mapping = value.to_dict()
        mapping["ready_registry_count"] = 1
        with self.assertRaises(ValidationError):
            federation.federation_from_mapping(mapping)

    def test_runtime_mapping_rejects_stage_order_drift(self):
        value = self.build_federation()
        mapping = value.runtime.to_dict()
        mapping["stages"][0]["ordinal"] = 4
        with self.assertRaises(ValidationError):
            federation.federation_runtime_from_mapping(mapping)

    def test_verification_mapping_rejects_check_order_drift(self):
        value = self.build_federation()
        mapping = value.verification.to_dict()
        mapping["checks"][0]["ordinal"] = 4
        with self.assertRaises(ValidationError):
            federation.federation_verification_from_mapping(mapping)

    def test_runtime_verification_rejects_stale_runtime(self):
        value = self.build_federation()
        value.runtime.content_address = "stale:runtime"
        receipt = federation.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_runtime(
            value.runtime, value, policy=value.policy, verification=value.verification
        )
        self.assertFalse(receipt.accepted)
        self.assertEqual(receipt.checks[0].kind, "runtime-address")

    def test_policy_address_is_conserved_through_federation(self):
        value = self.build_federation()
        self.assertEqual(value.policy_address, value.policy.content_address)
        self.assertEqual(value.verification.policy_address, value.policy.content_address)
        self.assertEqual(value.runtime.policy_address, value.policy.content_address)

    def test_no_public_projection_contains_attribution_fields(self):
        value = self.build_federation()
        projections = (
            value.to_dict(),
            value.policy.to_dict(),
            value.verification.to_dict(),
            value.runtime.to_dict(),
            federation.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_schema(),
            federation.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_capabilities(),
            federation.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_query_schema(),
            federation.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_verification_schema(),
            federation.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_runtime_schema(),
        )
        for projection in projections:
            text = json.dumps(projection).casefold()
            for forbidden in ("agent", "assistant", "author", "email", "generated_by", "language", "model", "private", "secret", "token", "user"):
                self.assertNotIn(forbidden, text)


class FederationContractTests(FederationFixture):
    def test_schema_and_capability_contracts_are_detailed(self):
        schema = federation.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_schema()
        capabilities = federation.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_capabilities()
        policy_schema = federation.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_policy_schema()
        policy_capabilities = federation.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_policy_capabilities()
        query_schema = federation.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_query_schema()
        query_capabilities = federation.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_query_capabilities()
        verification_schema = federation.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_verification_schema()
        verification_capabilities = federation.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_verification_capabilities()
        runtime_schema = federation.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_runtime_schema()
        runtime_capabilities = federation.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_runtime_capabilities()
        self.assertEqual(schema["exact_files"], ["manifest.json", "federation.json", "registries.json", "policy.json", "verification.json", "runtime.json"])
        self.assertEqual(schema["maximum_registries"], 64)
        self.assertEqual(schema["maximum_packets"], 4096)
        self.assertEqual(query_schema["resources"], ["summary", "registries", "packet-rollup", "verification", "policy-checks", "stages"])
        self.assertEqual(policy_schema["boundary"], "public_registry_federation_policy")
        self.assertTrue(capabilities["deterministic_order"])
        self.assertTrue(capabilities["independent_verification"])
        self.assertTrue(policy_capabilities["minimum_and_maximum_registry_limits"])
        self.assertTrue(query_capabilities["pagination"])
        self.assertTrue(verification_schema["independent"])
        self.assertTrue(verification_capabilities["address_recomputation"])
        self.assertEqual(len(runtime_schema["stages"]), 5)
        self.assertTrue(runtime_capabilities["replayable"])

    def test_contract_documentaries_are_canonical_json(self):
        functions = (
            federation.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_schema,
            federation.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_capabilities,
            federation.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_policy_schema,
            federation.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_policy_capabilities,
            federation.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_query_schema,
            federation.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_query_capabilities,
            federation.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_verification_schema,
            federation.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_verification_capabilities,
            federation.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_runtime_schema,
            federation.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_runtime_capabilities,
        )
        for builder in functions:
            with self.subTest(builder=builder.__name__):
                value = builder()
                raw = canonical_bytes(value)
                self.assertEqual(json.loads(raw), value)
                self.assertNotIn("agent", raw.decode("utf-8").casefold())

    def test_schema_capability_addresses_are_not_data_paths(self):
        schema = federation.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_schema()
        capabilities = federation.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_capabilities()
        combined = json.dumps({"schema": schema, "capabilities": capabilities}).casefold()
        self.assertNotIn("source_path", combined)
        self.assertNotIn("filesystem", combined)


class FederationCliTests(FederationFixture):
    base = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-packet-registry-federation"

    @staticmethod
    def cli_json(arguments):
        output = StringIO()
        with redirect_stdout(output):
            status = main(arguments)
        return status, json.loads(output.getvalue())

    def test_cli_contract_commands(self):
        for suffix in (
            "-schema",
            "-capabilities",
            "-policy-schema",
            "-policy-capabilities",
            "-query-schema",
            "-query-capabilities",
            "-verification-schema",
            "-verification-capabilities",
            "-runtime-schema",
            "-runtime-capabilities",
        ):
            status, value = self.cli_json([self.base + suffix])
            self.assertEqual(status, 0, suffix)
            self.assertTrue(value, suffix)

    def test_cli_build_query_verify_and_runtime(self):
        with tempfile.TemporaryDirectory() as root:
            first = registry.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
                self.build_named_registry("registry:cli-a", ("packet:cli-a",)), Path(root) / "registry-a"
            )
            second = registry.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
                self.build_named_registry("registry:cli-b", ("packet:cli-b",)), Path(root) / "registry-b"
            )
            destination = Path(root) / "federation"
            status, summary = self.cli_json(
                [
                    self.base,
                    "--registry-directory",
                    str(first),
                    "--registry-directory",
                    str(second),
                    "--federation-id",
                    "federation:cli",
                    "--destination",
                    str(destination),
                    "--format",
                    "summary",
                ]
            )
            self.assertEqual(status, 0)
            self.assertEqual(summary["federation_id"], "federation:cli")
            self.assertEqual(summary["registry_count"], 2)
            status, query = self.cli_json([self.base + "-query", "--input", str(destination), "--resource", "registries", "--state", "ready"])
            self.assertEqual(status, 0)
            self.assertEqual(query["total"], 2)
            status, verification = self.cli_json([self.base + "-verify", "--input", str(destination)])
            self.assertEqual(status, 0)
            self.assertTrue(verification["accepted"])
            status, runtime = self.cli_json([self.base + "-runtime", "--input", str(destination)])
            self.assertEqual(status, 0)
            self.assertEqual(runtime["state"], "ready")
            self.assertEqual(runtime["stage_count"], 5)

    def test_cli_build_exports_are_nonempty(self):
        with tempfile.TemporaryDirectory() as root:
            first = registry.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
                self.build_named_registry("registry:cli-format", ("packet:cli-format",)), Path(root) / "registry"
            )
            for output_format, marker in (
                ("json", '"federation_id"'),
                ("csv", "registry_id"),
                ("markdown", "# Observatory Packet Registry Federation"),
            ):
                output = StringIO()
                with redirect_stdout(output):
                    status = main([self.base, "--registry-directory", str(first), "--format", output_format])
                self.assertEqual(status, 0)
                self.assertIn(marker, output.getvalue())

    def test_cli_policy_arguments_can_hold_without_crashing(self):
        with tempfile.TemporaryDirectory() as root:
            first = registry.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
                self.build_named_registry("registry:cli-policy", ("packet:cli-policy",)), Path(root) / "registry"
            )
            output = StringIO()
            with redirect_stdout(output):
                status = main([self.base, "--registry-directory", str(first), "--minimum-registries", "2", "--format", "summary"])
            self.assertEqual(status, 2)
            summary = json.loads(output.getvalue())
            self.assertEqual(summary["registry_count"], 1)


class FederationApiTests(FederationFixture):
    base = "/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/observatory/packet/registry/federation"

    def start_server(self, root):
        server = create_server("127.0.0.1", 0, Path(root) / "api-data")
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server, thread

    def test_api_contract_resources(self):
        with tempfile.TemporaryDirectory() as root:
            server, thread = self.start_server(root)
            try:
                for suffix in (
                    "/schema",
                    "/capabilities",
                    "/query/schema",
                    "/query/capabilities",
                    "/verification/schema",
                    "/verification/capabilities",
                    "/runtime/schema",
                    "/runtime/capabilities",
                ):
                    status, content_type, value = self.http_json(server, self.base + suffix)
                    self.assertEqual(status, 200, suffix)
                    self.assertIn("application/json", content_type)
                    self.assertTrue(value, suffix)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_api_build_load_query_verify_and_runtime(self):
        with tempfile.TemporaryDirectory() as root:
            first = registry.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
                self.build_named_registry("registry:api-a", ("packet:api-a",)), Path(root) / "registry-a"
            )
            second = registry.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
                self.build_named_registry("registry:api-b", ("packet:api-b",)), Path(root) / "registry-b"
            )
            server, thread = self.start_server(root)
            try:
                status, _, summary = self.http_json(server, self.base, {"registry_directory": (str(first), str(second))})
                self.assertEqual(status, 200)
                self.assertEqual(summary["registry_count"], 2)
                self.assertEqual(summary["total_packet_count"], 2)
                status, _, query = self.http_json(server, self.base + "/query", {"registry_directory": (str(first), str(second)), "resource": "registries", "limit": "1"})
                self.assertEqual(status, 200)
                self.assertEqual(query["total"], 2)
                self.assertEqual(len(query["items"]), 1)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_api_persisted_input_verify_and_runtime(self):
        with tempfile.TemporaryDirectory() as root:
            first = registry.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
                self.build_named_registry("registry:api-persisted-a", ("packet:api-persisted-a",)), Path(root) / "registry-a"
            )
            second = registry.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
                self.build_named_registry("registry:api-persisted-b", ("packet:api-persisted-b",)), Path(root) / "registry-b"
            )
            value = federation.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_from_directories((first, second))
            destination = self.write_federation(value, Path(root) / "federation")
            server, thread = self.start_server(root)
            try:
                status, _, summary = self.http_json(server, self.base, {"input": str(destination)})
                self.assertEqual(status, 200)
                self.assertEqual(summary["registry_count"], 2)
                status, _, verification = self.http_json(server, self.base + "/verify", {"input": str(destination)})
                self.assertEqual(status, 200)
                self.assertTrue(verification["accepted"])
                status, _, runtime = self.http_json(server, self.base + "/runtime", {"input": str(destination)})
                self.assertEqual(status, 200)
                self.assertEqual(runtime["state"], "ready")
                status, _, query = self.http_json(server, self.base + "/query", {"input": str(destination), "resource": "packet-rollup", "text": "registry:api-persisted-a"})
                self.assertEqual(status, 200)
                self.assertEqual(query["total"], 1)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_api_csv_and_markdown_are_text_responses(self):
        with tempfile.TemporaryDirectory() as root:
            first = registry.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
                self.build_named_registry("registry:api-format", ("packet:api-format",)), Path(root) / "registry"
            )
            server, thread = self.start_server(root)
            try:
                for output_format, marker in (
                    ("csv", "registry_id"),
                    ("markdown", "# Observatory Packet Registry Federation"),
                ):
                    status, content_type, body = self.http_text(server, self.base, {"registry_directory": str(first), "format": output_format})
                    self.assertEqual(status, 200)
                    self.assertTrue(content_type)
                    self.assertIn(marker, body)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


class FederationRealDataTests(FederationFixture):
    def test_real_downloaded_packet_registries_form_a_federation(self):
        source = self.real_packet()
        if not source.is_dir():
            self.skipTest("retained downloaded packet fixture is not installed")
        with tempfile.TemporaryDirectory() as root:
            history_value = history.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_from_directories(
                source, source, history_id="history:federation-real"
            )
            history_directory = self.write_history(root, history_value, "real-history")
            first_packet = packet.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_from_history_directories(
                (history_directory, history_directory),
                observation_ids=("real-federation-baseline", "real-federation-rerun"),
                packet_id="packet:federation-real-a",
            )
            second_packet = packet.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_from_history_directories(
                (history_directory, history_directory),
                observation_ids=("real-federation-baseline-2", "real-federation-rerun-2"),
                packet_id="packet:federation-real-b",
            )
            first_registry = registry.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
                (first_packet,), registry_id="registry:federation-real-a"
            )
            second_registry = registry.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
                (second_packet,), registry_id="registry:federation-real-b"
            )
            first_directory = registry.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
                first_registry, Path(root) / "real-registry-a"
            )
            second_directory = registry.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
                second_registry, Path(root) / "real-registry-b"
            )
            value = federation.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_from_directories(
                (second_directory, first_directory), federation_id="federation:real"
            )
            destination = self.write_federation(value, Path(root) / "real-federation")
            loaded = federation.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(destination)
            self.assertTrue(loaded.accepted)
            self.assertTrue(loaded.release_ready)
            self.assertEqual(loaded.registry_count, 2)
            self.assertEqual(loaded.total_packet_count, 2)
            self.assertEqual(loaded.verification.failed_count, 0)
            self.assertEqual(loaded.runtime.policy_failed_count, 0)
            self.assertEqual(
                [entry.registry_id for entry in loaded.entries],
                ["registry:federation-real-a", "registry:federation-real-b"],
            )

    def test_real_downloaded_federation_query_is_path_free(self):
        source = self.real_packet()
        if not source.is_dir():
            self.skipTest("retained downloaded packet fixture is not installed")
        with tempfile.TemporaryDirectory() as root:
            history_value = history.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_from_directories(
                source, source, history_id="history:federation-query-real"
            )
            history_directory = self.write_history(root, history_value, "history")
            packet_value = packet.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_from_history_directories(
                (history_directory, history_directory),
                observation_ids=("query-real-a", "query-real-b"),
                packet_id="packet:query-real",
            )
            registry_value = registry.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
                (packet_value,), registry_id="registry:query-real"
            )
            value = federation.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(
                (registry_value,), federation_id="federation:query-real"
            )
            result = federation.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(
                value, resource="packet-rollup", text="query-real"
            )
            rendered = json.dumps(result.to_dict()).casefold()
            self.assertEqual(result.total, 1)
            self.assertNotIn(str(source).casefold(), rendered)
            self.assertNotIn("agent", rendered)
            self.assertNotIn("language", rendered)


class FederationDeepCoverageTests(FederationFixture):
    def test_default_policy_is_bounded_and_public(self):
        policy = federation.default_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_policy()
        self.assertEqual(policy.minimum_registries, 1)
        self.assertEqual(policy.maximum_registries, 64)
        self.assertEqual(policy.maximum_packets, 4096)
        self.assertEqual(policy.maximum_blocked_registries, 0)
        self.assertEqual(policy.maximum_held_registries, 64)
        self.assertTrue(policy.require_all_registries_accepted)
        self.assertTrue(policy.require_all_release_ready)
        self.assertFalse(policy.allow_empty)
        self.assertNotIn("agent", json.dumps(policy.to_dict()).casefold())

    def test_policy_addresses_change_only_when_policy_content_changes(self):
        first = federation.default_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_policy(
            policy_id="policy:first"
        )
        second = federation.default_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_policy(
            policy_id="policy:second"
        )
        self.assertNotEqual(first.content_address, second.content_address)
        self.assertNotEqual(first.to_dict(), second.to_dict())
        self.assertEqual(
            federation.address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_policy(
                first
            ),
            first.content_address,
        )

    def test_policy_flag_matrix_is_serializable(self):
        policies = []
        for accepted_required in (False, True):
            for ready_required in (False, True):
                for allow_empty in (False, True):
                    policy = federation.default_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_policy(
                        policy_id=f"policy:{accepted_required}:{ready_required}:{allow_empty}",
                        minimum_registries=0 if allow_empty else 1,
                        require_all_registries_accepted=accepted_required,
                        require_all_release_ready=ready_required,
                        allow_empty=allow_empty,
                    )
                    policies.append(policy)
                    self.assertEqual(
                        federation.federation_policy_from_mapping(policy.to_dict()).to_dict(),
                        policy.to_dict(),
                    )
        self.assertEqual(len(policies), 8)
        self.assertEqual(len({policy.content_address for policy in policies}), 8)

    def test_entry_rollups_match_the_hydrated_registry_objects(self):
        value = self.build_federation()
        for entry, source in zip(value.entries, value.registries, strict=True):
            self.assertEqual(entry.registry_id, source.registry_id)
            self.assertEqual(entry.registry_address, source.content_address)
            self.assertEqual(entry.state, source.state)
            self.assertEqual(entry.accepted, source.accepted)
            self.assertEqual(entry.release_ready, source.release_ready)
            self.assertEqual(entry.packet_count, source.packet_count)
            self.assertEqual(entry.ready_packet_count, source.ready_count)
            self.assertEqual(entry.held_packet_count, source.held_count)
            self.assertEqual(entry.blocked_packet_count, source.blocked_count)
            self.assertEqual(entry.accepted_packet_count, source.accepted_count)
            self.assertEqual(entry.release_ready_packet_count, source.release_ready_count)

    def test_hydrated_verification_checks_registry_links(self):
        value = self.build_federation()
        receipt = federation.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(
            value, registries=value.registries, policy=value.policy
        )
        self.assertTrue(receipt.accepted)
        self.assertTrue(receipt.checks[18].passed)
        self.assertEqual(receipt.checks[18].kind, "registry-links")

    def test_verification_reports_wrong_hydrated_registry_set(self):
        value = self.build_federation()
        wrong = self.build_named_registry("registry:wrong", ("packet:wrong",))
        receipt = federation.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(value, registries=(wrong,), policy=value.policy)
        self.assertFalse(receipt.accepted)
        self.assertFalse(receipt.checks[18].passed)
        self.assertEqual(receipt.checks[18].kind, "registry-links")

    def test_verification_reports_mutated_entry_address(self):
        value = self.build_federation()
        value.entries[0].content_address = "tampered:entry"
        receipt = federation.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(value, registries=value.registries, policy=value.policy)
        self.assertFalse(receipt.accepted)
        self.assertFalse(receipt.checks[17].passed)
        self.assertEqual(receipt.checks[17].kind, "entry-addresses")

    def test_verification_reports_mutated_policy_link(self):
        value = self.build_federation()
        other_policy = federation.default_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_policy(policy_id="policy:other")
        receipt = federation.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(value, registries=value.registries, policy=other_policy)
        self.assertFalse(receipt.accepted)
        self.assertFalse(receipt.checks[16].passed)
        self.assertEqual(receipt.checks[16].kind, "policy-link")

    def test_ready_runtime_stage_states_are_all_passed(self):
        value = self.build_federation()
        self.assertEqual([stage.state for stage in value.runtime.stages], ["passed"] * 5)
        self.assertEqual(value.runtime.policy_passed_count, 8)
        self.assertEqual(value.runtime.policy_failed_count, 0)

    def test_held_runtime_stage_states_preserve_a_held_terminal_projection(self):
        policy = federation.default_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_policy(
            policy_id="policy:held-stage",
            require_all_release_ready=False,
        )
        value = federation.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(
            (self.build_held_registry(),), federation_id="federation:held-stage", policy=policy
        )
        self.assertEqual(value.runtime.state, "held")
        self.assertEqual([stage.state for stage in value.runtime.stages], ["passed"] * 4 + ["held"])
        self.assertTrue(value.runtime.policy_checks[6].passed)

    def test_blocked_runtime_stage_states_preserve_policy_failure(self):
        value = federation.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(
            (self.build_blocked_registry(),), federation_id="federation:blocked-stage"
        )
        self.assertEqual(value.runtime.state, "blocked")
        self.assertEqual(value.runtime.stages[0].state, "passed")
        self.assertEqual(value.runtime.stages[1].state, "passed")
        self.assertEqual(value.runtime.stages[2].state, "blocked")
        self.assertEqual(value.runtime.stages[3].state, "blocked")
        self.assertEqual(value.runtime.stages[4].state, "blocked")

    def test_runtime_stage_addresses_form_a_valid_chain(self):
        value = self.build_federation()
        stages = value.runtime.stages
        self.assertIsNone(stages[0].input_address)
        for previous, current in zip(stages, stages[1:]):
            self.assertEqual(current.input_address, previous.output_address)
        self.assertEqual(stages[-1].output_address, value.content_address)
        for stage in stages:
            self.assertEqual(
                federation.address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_stage(stage),
                stage.content_address,
            )

    def test_runtime_query_can_select_only_passed_stages(self):
        value = self.build_federation()
        result = federation.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(value, resource="stages")
        self.assertEqual(result.total, 5)
        self.assertTrue(all(item["state"] == "passed" for item in result.items))

    def test_policy_query_can_select_one_check_by_text(self):
        value = self.build_federation()
        result = federation.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(value, resource="policy-checks", text="empty federation")
        self.assertEqual(result.total, 1)
        self.assertEqual(result.items[0]["kind"], "empty-federation")

    def test_query_accepts_an_explicit_typed_query(self):
        value = self.build_federation()
        query = federation.FederationQuery(resource="registries", state="ready", accepted=True, release_ready=True, offset=1, limit=1)
        result = federation.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(value, query)
        self.assertEqual(result.query.to_dict(), query.to_dict())
        self.assertEqual(result.total, 2)
        self.assertEqual(result.items[0]["registry_id"], "registry:b")

    def test_query_parameter_validation_rejects_nonboolean_filters(self):
        with self.assertRaises(ValidationError):
            federation.FederationQuery(resource="registries", accepted="yes")
        with self.assertRaises(ValidationError):
            federation.FederationQuery(resource="registries", release_ready=1)
        with self.assertRaises(ValidationError):
            federation.FederationQuery(resource="registries", offset=True)
        with self.assertRaises(ValidationError):
            federation.FederationQuery(resource="registries", limit=False)

    def test_query_result_address_recomputes(self):
        value = self.build_federation()
        result = federation.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(value, resource="verification")
        self.assertEqual(
            federation.address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_query(result),
            result.content_address,
        )
        self.assertEqual(result.query.resource, "verification")

    def test_query_result_constructor_rejects_untyped_query(self):
        value = self.build_federation()
        with self.assertRaises(ValidationError):
            federation.FederationQueryResult(
                federation_address=value.content_address,
                query=object(),
                total=0,
                offset=0,
                limit=1,
                items=(),
                content_address="bad:query",
            )

    def test_query_result_constructor_rejects_overlong_pages(self):
        value = self.build_federation()
        query = federation.FederationQuery(resource="registries", limit=1)
        with self.assertRaises(ValidationError):
            federation.FederationQueryResult(
                federation_address=value.content_address,
                query=query,
                total=1,
                offset=0,
                limit=1,
                items=(value.entries[0].to_dict(), value.entries[1].to_dict()),
                content_address="bad:page",
            )

    def test_query_exports_cover_all_resources(self):
        value = self.build_federation()
        for resource in ("summary", "registries", "packet-rollup", "verification", "policy-checks", "stages"):
            result = federation.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(value, resource=resource)
            encoded = federation.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_query_json(result)
            csv_text = federation.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_query_csv(result)
            markdown = federation.render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_query_markdown(result)
            self.assertEqual(json.loads(encoded), result.to_dict())
            self.assertTrue(csv_text.endswith("\n"))
            self.assertIn("# Observatory Packet Registry Federation Query", markdown)

    def test_each_persisted_document_is_canonical_after_writing(self):
        value = self.build_federation()
        with tempfile.TemporaryDirectory() as root:
            destination = self.write_federation(value, Path(root) / "federation")
            for path in destination.iterdir():
                raw = path.read_bytes()
                self.assertEqual(json.loads(raw), json.loads(raw.decode("utf-8")))
                self.assertEqual(canonical_bytes(json.loads(raw)), raw)

    def test_manifest_contains_one_receipt_for_each_payload_document(self):
        value = self.build_federation()
        with tempfile.TemporaryDirectory() as root:
            destination = self.write_federation(value, Path(root) / "federation")
            manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
            files = {row["file_name"] for row in manifest["artifact_files"]}
            self.assertEqual(manifest["artifact_count"], 5)
            self.assertEqual(files, {"federation.json", "registries.json", "policy.json", "verification.json", "runtime.json"})
            self.assertEqual(len(manifest["artifact_files"]), 5)
            self.assertEqual(manifest["federation_address"], value.content_address)
            self.assertEqual(manifest["verification_address"], value.verification_address)
            self.assertEqual(manifest["runtime_address"], value.runtime_address)

    def test_persisted_documents_do_not_include_input_locations(self):
        value = self.build_federation()
        with tempfile.TemporaryDirectory() as root:
            destination = self.write_federation(value, Path(root) / "federation")
            text = "\n".join(path.read_text(encoding="utf-8") for path in destination.iterdir()).casefold()
            self.assertNotIn(str(Path(root)).casefold(), text)
            self.assertNotIn("source_path", text)
            self.assertNotIn("agent", text)
            self.assertNotIn("language", text)

    def test_destination_file_is_rejected(self):
        value = self.build_federation()
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "not-a-directory"
            path.write_text("occupied", encoding="utf-8")
            with self.assertRaises(ValidationError):
                self.write_federation(value, path)

    def test_destination_symlink_is_rejected(self):
        value = self.build_federation()
        with tempfile.TemporaryDirectory() as root:
            existing = self.write_federation(value, Path(root) / "existing")
            link = Path(root) / "link"
            try:
                link.symlink_to(existing, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("directory symlinks are unavailable")
            with self.assertRaises(ValidationError):
                self.write_federation(value, link)

    def test_directory_builder_rejects_no_directories(self):
        with self.assertRaises(ValidationError):
            federation.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_from_directories(())

    def test_loaded_federation_queries_without_hydrated_registry_sources(self):
        value = self.build_federation()
        with tempfile.TemporaryDirectory() as root:
            destination = self.write_federation(value, Path(root) / "federation")
            loaded = federation.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(destination)
            self.assertEqual(loaded.registries, ())
            result = federation.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(loaded, resource="registries")
            self.assertEqual(result.total, 2)
            self.assertEqual(result.items[0]["registry_id"], "registry:a")

    def test_federation_ids_change_the_federation_address(self):
        first = self.build_federation(("registry:a", "registry:b"))
        second = federation.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(
            (self.build_named_registry("registry:a"), self.build_named_registry("registry:b")),
            federation_id="federation:other",
        )
        self.assertNotEqual(first.content_address, second.content_address)
        self.assertNotEqual(first.federation_id, second.federation_id)
        self.assertEqual(first.registry_count, second.registry_count)

    def test_policy_maximum_packet_boundary_accepts_exact_total(self):
        policy = federation.default_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_policy(
            policy_id="policy:exact-packets", maximum_packets=4
        )
        value = federation.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(
            (self.build_named_registry("registry:a"), self.build_named_registry("registry:b")),
            federation_id="federation:exact-packets",
            policy=policy,
        )
        self.assertTrue(value.runtime.accepted)
        self.assertEqual(value.runtime.policy_checks[2].observed, 4)

    def test_policy_maximum_registry_boundary_accepts_exact_count(self):
        policy = federation.default_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_policy(
            policy_id="policy:exact-registries", maximum_registries=2
        )
        value = federation.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(
            (self.build_named_registry("registry:a"), self.build_named_registry("registry:b")),
            federation_id="federation:exact-registries",
            policy=policy,
        )
        self.assertTrue(value.runtime.accepted)
        self.assertEqual(value.runtime.policy_checks[1].observed, 2)

    def test_query_text_matches_nested_public_values(self):
        value = self.build_federation()
        result = federation.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(value, resource="registries", text=value.entries[1].registry_address[-16:])
        self.assertEqual(result.total, 1)
        self.assertEqual(result.items[0]["registry_id"], "registry:b")

    def test_query_result_rejects_private_item_keys(self):
        value = self.build_federation()
        query = federation.FederationQuery(resource="summary", limit=1)
        with self.assertRaises(ValidationError):
            federation.FederationQueryResult(
                federation_address=value.content_address,
                query=query,
                total=1,
                offset=0,
                limit=1,
                items=({"agent": "forbidden"},),
                content_address="bad:public",
            )

    def test_runtime_mapping_rejects_private_policy_check_keys(self):
        value = self.build_federation()
        mapping = value.runtime.to_dict()
        mapping["policy_checks"][0]["model"] = "forbidden"
        with self.assertRaises(ValidationError):
            federation.federation_runtime_from_mapping(mapping)

    def test_federation_mapping_rejects_unknown_fields(self):
        value = self.build_federation()
        mapping = value.to_dict() | {"unknown_field": True}
        with self.assertRaises(ValidationError):
            federation.federation_from_mapping(mapping)

    def test_summary_excludes_entry_payloads_but_preserves_counts(self):
        value = self.build_federation()
        summary = value.summary()
        self.assertNotIn("entries", summary)
        self.assertEqual(summary["registry_count"], len(value.entries))
        self.assertEqual(summary["total_packet_count"], 4)
        self.assertEqual(summary["state"], "ready")

    def test_verification_of_loaded_value_does_not_need_source_packet_directories(self):
        value = self.build_federation()
        with tempfile.TemporaryDirectory() as root:
            destination = self.write_federation(value, Path(root) / "federation")
            loaded = federation.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(destination)
            verification = federation.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(loaded)
            self.assertTrue(verification.accepted)
            self.assertEqual(verification.federation_address, loaded.content_address)
            self.assertEqual(verification.policy_address, loaded.policy.content_address)

    def test_runtime_policy_check_details_are_human_readable(self):
        value = self.build_federation()
        for check in value.runtime.policy_checks:
            self.assertTrue(check.kind)
            self.assertTrue(check.detail)
            self.assertIsNotNone(check.expected)
            self.assertIsNotNone(check.observed)
            self.assertTrue(check.content_address.startswith("module-workbench"))

    def test_federation_entries_are_sorted_by_id_then_address(self):
        value = self.build_federation(("registry:z", "registry:a"))
        keys = [(entry.registry_id, entry.registry_address) for entry in value.entries]
        self.assertEqual(keys, sorted(keys))

    def test_all_addresses_have_nonempty_prefix_and_digest(self):
        value = self.build_federation()
        addresses = [value.content_address, value.policy_address, value.verification_address, value.runtime_address]
        addresses.extend(entry.content_address for entry in value.entries)
        addresses.extend(check.content_address for check in value.verification.checks)
        addresses.extend(stage.content_address for stage in value.runtime.stages)
        addresses.extend(check.content_address for check in value.runtime.policy_checks)
        self.assertTrue(all(":" in address and address.rsplit(":", 1)[1] for address in addresses))

    def test_real_data_federation_has_the_same_contract_as_fixture_data(self):
        source = self.real_packet()
        if not source.is_dir():
            self.skipTest("retained downloaded packet fixture is not installed")
        with tempfile.TemporaryDirectory() as root:
            history_value = history.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_from_directories(source, source, history_id="history:deep-real")
            history_directory = self.write_history(root, history_value, "history")
            packet_value = packet.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_from_history_directories((history_directory, history_directory), observation_ids=("deep-real-a", "deep-real-b"), packet_id="packet:deep-real")
            registry_value = registry.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry((packet_value,), registry_id="registry:deep-real")
            value = federation.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation((registry_value,), federation_id="federation:deep-real")
            self.assertTrue(value.accepted)
            self.assertTrue(value.release_ready)
            self.assertEqual(value.verification.failed_count, 0)
            self.assertEqual(value.runtime.policy_failed_count, 0)


class FederationOperationalMatrixTests(FederationFixture):
    def test_ready_held_blocked_state_matrix_is_explicit(self):
        ready = self.build_federation(("registry:matrix-ready",))
        held_policy = federation.default_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_policy(
            policy_id="policy:matrix-held", require_all_release_ready=False
        )
        held = federation.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(
            (self.build_held_registry("registry:matrix-held"),),
            federation_id="federation:matrix-held",
            policy=held_policy,
        )
        blocked = federation.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(
            (self.build_blocked_registry("registry:matrix-blocked"),),
            federation_id="federation:matrix-blocked",
        )
        self.assertEqual(ready.state, "ready")
        self.assertEqual(held.state, "held")
        self.assertEqual(blocked.state, "blocked")
        self.assertEqual(ready.runtime.state, "ready")
        self.assertEqual(held.runtime.state, "held")
        self.assertEqual(blocked.runtime.state, "blocked")

    def test_held_query_exposes_accepted_but_not_release_ready_rows(self):
        policy = federation.default_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_policy(
            policy_id="policy:held-query-matrix", require_all_release_ready=False
        )
        value = federation.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(
            (self.build_held_registry("registry:held-query-matrix"),),
            federation_id="federation:held-query-matrix",
            policy=policy,
        )
        result = federation.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(
            value,
            resource="registries",
            state="held",
            accepted=True,
            release_ready=False,
        )
        self.assertEqual(result.total, 1)
        self.assertTrue(result.items[0]["accepted"])
        self.assertFalse(result.items[0]["release_ready"])

    def test_blocked_query_exposes_blocked_packet_rollup(self):
        value = federation.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(
            (self.build_blocked_registry("registry:blocked-query-matrix"),),
            federation_id="federation:blocked-query-matrix",
        )
        result = federation.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(
            value, resource="packet-rollup", state="blocked"
        )
        self.assertEqual(result.total, 1)
        self.assertEqual(result.items[0]["blocked_packet_count"], 1)
        self.assertFalse(value.runtime.accepted)

    def test_empty_query_has_a_single_empty_summary(self):
        policy = federation.default_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_policy(
            policy_id="policy:empty-query-matrix", minimum_registries=0, allow_empty=True
        )
        value = federation.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(
            (), federation_id="federation:empty-query-matrix", policy=policy
        )
        result = federation.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(
            value, resource="summary", state="empty"
        )
        self.assertEqual(result.total, 1)
        self.assertEqual(result.items[0]["registry_count"], 0)
        self.assertEqual(result.items[0]["state"], "empty")

    def test_policy_check_rows_have_conserved_ordinals(self):
        value = self.build_federation()
        result = federation.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(
            value, resource="policy-checks"
        )
        self.assertEqual([row["ordinal"] for row in result.items], list(range(8)))
        self.assertEqual(sum(row["passed"] for row in result.items), 8)
        self.assertEqual(sum(not row["passed"] for row in result.items), 0)

    def test_policy_check_rows_can_be_paged_one_at_a_time(self):
        value = self.build_federation()
        pages = []
        for offset in range(8):
            result = federation.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(
                value, resource="policy-checks", offset=offset, limit=1
            )
            self.assertEqual(result.total, 8)
            self.assertEqual(len(result.items), 1)
            pages.append(result.items[0]["kind"])
        self.assertEqual(pages[0], "minimum-registries")
        self.assertEqual(pages[-1], "empty-federation")

    def test_stage_query_rows_can_be_paged_without_reordering(self):
        value = self.build_federation()
        all_rows = federation.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(
            value, resource="stages", limit=5
        ).items
        first = federation.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(
            value, resource="stages", offset=0, limit=2
        ).items
        second = federation.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(
            value, resource="stages", offset=2, limit=3
        ).items
        self.assertEqual(first + second, all_rows)
        self.assertEqual([row["name"] for row in first], ["load", "verify"])
        self.assertEqual([row["name"] for row in second], ["policy", "project", "complete"])

    def test_mapping_round_trips_preserve_every_public_address(self):
        value = self.build_federation()
        restored = federation.federation_from_mapping(value.to_dict())
        self.assertEqual(restored.content_address, value.content_address)
        for original, copy in zip(value.entries, restored.entries, strict=True):
            self.assertEqual(copy.content_address, original.content_address)
        for original, copy in zip(value.verification.checks, value.verification.checks, strict=True):
            self.assertEqual(copy.content_address, original.content_address)
        runtime = federation.federation_runtime_from_mapping(value.runtime.to_dict())
        self.assertEqual([stage.content_address for stage in runtime.stages], [stage.content_address for stage in value.runtime.stages])

    def test_every_public_receipt_has_a_content_address(self):
        value = self.build_federation()
        receipts = [value, value.policy, value.verification, value.runtime]
        receipts.extend(value.entries)
        receipts.extend(value.verification.checks)
        receipts.extend(value.runtime.stages)
        receipts.extend(value.runtime.policy_checks)
        for receipt in receipts:
            self.assertIsInstance(receipt.content_address, str)
            self.assertTrue(receipt.content_address)
            self.assertNotIn("pending:", receipt.content_address)

    def test_federation_to_dict_keeps_entries_in_ordinal_order(self):
        value = self.build_federation(("registry:b", "registry:a"))
        mapping = value.to_dict()
        self.assertEqual([entry["ordinal"] for entry in mapping["entries"]], [0, 1])
        self.assertEqual([entry["registry_id"] for entry in mapping["entries"]], ["registry:a", "registry:b"])

    def test_federation_summary_has_only_scalar_and_receipt_fields(self):
        value = self.build_federation()
        summary = value.summary()
        self.assertTrue(all(not isinstance(item, (list, dict, tuple)) for item in summary.values()))
        self.assertEqual(summary["registry_count"], 2)
        self.assertEqual(summary["ready_packet_count"], 4)
        self.assertEqual(summary["accepted"], True)

    def test_each_persisted_payload_is_reloadable_individually_as_json(self):
        value = self.build_federation()
        with tempfile.TemporaryDirectory() as root:
            destination = self.write_federation(value, Path(root) / "federation")
            for file_name in ("federation.json", "registries.json", "policy.json", "verification.json", "runtime.json"):
                document = json.loads((destination / file_name).read_text(encoding="utf-8"))
                self.assertIsInstance(document, dict)
                self.assertNotIn("path", json.dumps(document).casefold())

    def test_manifest_receipts_track_actual_payload_lengths(self):
        value = self.build_federation()
        with tempfile.TemporaryDirectory() as root:
            destination = self.write_federation(value, Path(root) / "federation")
            manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
            for row in manifest["artifact_files"]:
                payload = destination / row["file_name"]
                self.assertEqual(row["byte_count"], payload.stat().st_size)
                self.assertEqual(row["byte_address"].split(":", 1)[0], federation.MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_PREFIX + "-" + row["kind"] + "-bytes")

    def test_overwrite_replaces_a_tampered_directory_atomically(self):
        value = self.build_federation()
        with tempfile.TemporaryDirectory() as root:
            destination = self.write_federation(value, Path(root) / "federation")
            (destination / "extra.tmp").write_text("tamper", encoding="utf-8")
            self.write_federation(value, destination, overwrite=True)
            self.assertNotIn("extra.tmp", {path.name for path in destination.iterdir()})
            loaded = federation.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(destination)
            self.assertEqual(loaded.content_address, value.content_address)

    def test_loaded_runtime_verification_replays_exactly(self):
        value = self.build_federation()
        with tempfile.TemporaryDirectory() as root:
            destination = self.write_federation(value, Path(root) / "federation")
            loaded = federation.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(destination)
            receipt = federation.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_runtime(
                loaded.runtime,
                loaded,
                policy=loaded.policy,
                verification=loaded.verification,
            )
            self.assertTrue(receipt.accepted)
            self.assertEqual(receipt.failed_count, 0)

    def test_loaded_verification_and_runtime_addresses_are_manifest_links(self):
        value = self.build_federation()
        with tempfile.TemporaryDirectory() as root:
            destination = self.write_federation(value, Path(root) / "federation")
            manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
            loaded = federation.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(destination)
            self.assertEqual(manifest["verification_address"], loaded.verification_address)
            self.assertEqual(manifest["runtime_address"], loaded.runtime_address)
            self.assertEqual(manifest["policy_address"], loaded.policy_address)

    def test_registry_directory_order_does_not_change_directory_build_result(self):
        with tempfile.TemporaryDirectory() as root:
            first = registry.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(self.build_named_registry("registry:order-a", ("packet:order-a",)), Path(root) / "a")
            second = registry.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(self.build_named_registry("registry:order-b", ("packet:order-b",)), Path(root) / "b")
            left = federation.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_from_directories((first, second))
            right = federation.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_from_directories((second, first))
            self.assertEqual(left.to_dict(), right.to_dict())

    def test_cli_query_supports_json_csv_and_markdown(self):
        with tempfile.TemporaryDirectory() as root:
            registry_directory = registry.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(self.build_named_registry("registry:cli-query-formats", ("packet:cli-query-formats",)), Path(root) / "registry")
            value = federation.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_from_directories((registry_directory,))
            destination = self.write_federation(value, Path(root) / "federation")
            for output_format, marker in (("json", '"items"'), ("csv", "registry_id"), ("markdown", "# Observatory Packet Registry Federation Query")):
                output = StringIO()
                with redirect_stdout(output):
                    status = main([self.cli_base + "-query", "--input", str(destination), "--resource", "registries", "--format", output_format])
                self.assertEqual(status, 0)
                self.assertIn(marker, output.getvalue())

    @property
    def cli_base(self):
        return "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-packet-registry-federation"

    def test_cli_allow_existing_replaces_a_prior_federation(self):
        with tempfile.TemporaryDirectory() as root:
            registry_directory = registry.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(self.build_named_registry("registry:cli-overwrite", ("packet:cli-overwrite",)), Path(root) / "registry")
            destination = Path(root) / "federation"
            arguments = [self.cli_base, "--registry-directory", str(registry_directory), "--destination", str(destination), "--format", "summary"]
            self.assertEqual(main(arguments), 0)
            self.assertEqual(main(arguments[:-2] + ["--allow-existing", "--format", "summary"]), 0)
            self.assertTrue((destination / "runtime.json").is_file())

    def test_api_query_all_resources_returns_addressed_pages(self):
        with tempfile.TemporaryDirectory() as root:
            registry_directory = registry.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(self.build_named_registry("registry:api-resources", ("packet:api-resources",)), Path(root) / "registry")
            value = federation.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_from_directories((registry_directory,))
            destination = self.write_federation(value, Path(root) / "federation")
            server, thread = create_server("127.0.0.1", 0, Path(root) / "api-data"), None
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                for resource in ("summary", "registries", "packet-rollup", "verification", "policy-checks", "stages"):
                    status, _, payload = self.http_json(server, self.api_base + "/query", {"input": str(destination), "resource": resource})
                    self.assertEqual(status, 200, resource)
                    self.assertIn("content_address", payload)
                    self.assertIn("total", payload)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    @property
    def api_base(self):
        return "/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/observatory/packet/registry/federation"

    def test_api_can_render_query_csv_and_markdown_from_input(self):
        with tempfile.TemporaryDirectory() as root:
            registry_directory = registry.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(self.build_named_registry("registry:api-formats", ("packet:api-formats",)), Path(root) / "registry")
            value = federation.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_from_directories((registry_directory,))
            destination = self.write_federation(value, Path(root) / "federation")
            server = create_server("127.0.0.1", 0, Path(root) / "api-data")
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                for output_format, marker in (("csv", "registry_id"), ("markdown", "# Observatory Packet Registry Federation Query")):
                    status, content_type, body = self.http_text(server, self.api_base + "/query", {"input": str(destination), "resource": "registries", "format": output_format})
                    self.assertEqual(status, 200)
                    self.assertTrue(content_type)
                    self.assertIn(marker, body)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


class FederationFinalBoundaryTests(FederationFixture):
    api_base = "/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/observatory/packet/registry/federation"
    cli_base = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-packet-registry-federation"

    def test_api_returns_unprocessable_for_policy_blocked_build(self):
        with tempfile.TemporaryDirectory() as root:
            registry_directory = registry.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
                self.build_named_registry("registry:api-blocked", ("packet:api-blocked",)), Path(root) / "registry"
            )
            server = create_server("127.0.0.1", 0, Path(root) / "api-data")
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                status, _, payload = self.http_json(server, self.api_base, {"registry_directory": str(registry_directory), "minimum_registries": "2"})
                self.assertEqual(status, 422)
                self.assertEqual(payload["registry_count"], 1)
                self.assertTrue(payload["accepted"])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_api_runtime_returns_blocked_policy_receipt(self):
        with tempfile.TemporaryDirectory() as root:
            registry_directory = registry.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
                self.build_named_registry("registry:api-runtime-blocked", ("packet:api-runtime-blocked",)), Path(root) / "registry"
            )
            policy = federation.default_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_policy(
                policy_id="policy:api-runtime-blocked", minimum_registries=2
            )
            value = federation.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(
                (registry.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(registry_directory),),
                federation_id="federation:api-runtime-blocked",
                policy=policy,
            )
            destination = self.write_federation(value, Path(root) / "federation")
            server = create_server("127.0.0.1", 0, Path(root) / "api-data")
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                status, _, runtime = self.http_json(server, self.api_base + "/runtime", {"input": str(destination)})
                self.assertEqual(status, 422)
                self.assertEqual(runtime["state"], "blocked")
                self.assertFalse(runtime["accepted"])
                self.assertGreater(runtime["policy_failed_count"], 0)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_cli_summary_does_not_echo_registry_directory(self):
        with tempfile.TemporaryDirectory() as root:
            registry_directory = registry.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
                self.build_named_registry("registry:cli-path", ("packet:cli-path",)), Path(root) / "registry"
            )
            output = StringIO()
            with redirect_stdout(output):
                status = main([self.cli_base, "--registry-directory", str(registry_directory), "--format", "summary"])
            self.assertEqual(status, 0)
            self.assertNotIn(str(registry_directory), output.getvalue())
            self.assertIn('"registry_count"', output.getvalue())

    def test_cli_verify_output_is_a_structural_receipt(self):
        with tempfile.TemporaryDirectory() as root:
            registry_directory = registry.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
                self.build_named_registry("registry:cli-verify", ("packet:cli-verify",)), Path(root) / "registry"
            )
            value = federation.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_from_directories((registry_directory,))
            destination = self.write_federation(value, Path(root) / "federation")
            output = StringIO()
            with redirect_stdout(output):
                status = main([self.cli_base + "-verify", "--input", str(destination)])
            self.assertEqual(status, 0)
            payload = json.loads(output.getvalue())
            self.assertEqual(payload["check_count"], 20)
            self.assertEqual(payload["failed_count"], 0)
            self.assertTrue(payload["accepted"])

    def test_manifest_artifact_count_tamper_is_rejected(self):
        value = self.build_federation()
        with tempfile.TemporaryDirectory() as root:
            destination = self.write_federation(value, Path(root) / "federation")
            path = destination / "manifest.json"
            manifest = json.loads(path.read_text(encoding="utf-8"))
            manifest["artifact_count"] = 4
            manifest["manifest_address"] = federation.content_hash(
                manifest | {"manifest_address": None},
                prefix=federation.MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_PREFIX + "-manifest",
            )
            path.write_bytes(canonical_bytes(manifest))
            with self.assertRaises(ValidationError):
                federation.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(destination)

    def test_manifest_artifact_file_set_tamper_is_rejected(self):
        value = self.build_federation()
        with tempfile.TemporaryDirectory() as root:
            destination = self.write_federation(value, Path(root) / "federation")
            path = destination / "manifest.json"
            manifest = json.loads(path.read_text(encoding="utf-8"))
            manifest["artifact_files"][0]["file_name"] = "unknown.json"
            manifest["manifest_address"] = federation.content_hash(
                manifest | {"manifest_address": None},
                prefix=federation.MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_REGISTRY_FEDERATION_PREFIX + "-manifest",
            )
            path.write_bytes(canonical_bytes(manifest))
            with self.assertRaises(ValidationError):
                federation.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(destination)

    def test_federation_query_result_keeps_total_when_limit_is_one(self):
        value = self.build_federation()
        result = federation.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(value, resource="registries", limit=1)
        self.assertEqual(result.total, 2)
        self.assertEqual(result.limit, 1)
        self.assertEqual(len(result.items), 1)
        self.assertEqual(result.offset, 0)

    def test_federation_query_result_offset_at_total_is_empty(self):
        value = self.build_federation()
        result = federation.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(value, resource="registries", offset=2, limit=1)
        self.assertEqual(result.total, 2)
        self.assertEqual(result.items, ())
        self.assertEqual(result.offset, 2)

    def test_federation_query_result_content_address_includes_query_shape(self):
        value = self.build_federation()
        first = federation.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(value, resource="registries", state="ready")
        second = federation.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation(value, resource="registries", state="ready", limit=1)
        self.assertNotEqual(first.content_address, second.content_address)
        self.assertNotEqual(first.query.to_dict(), second.query.to_dict())

    def test_policy_check_addresses_are_unique(self):
        value = self.build_federation()
        addresses = [check.content_address for check in value.runtime.policy_checks]
        self.assertEqual(len(addresses), len(set(addresses)))
        self.assertEqual(len(addresses), value.runtime.policy_check_count)

    def test_verification_check_addresses_are_unique(self):
        value = self.build_federation()
        addresses = [check.content_address for check in value.verification.checks]
        self.assertEqual(len(addresses), len(set(addresses)))
        self.assertEqual(len(addresses), value.verification.check_count)

    def test_runtime_stage_names_are_unique_and_ordered(self):
        value = self.build_federation()
        names = [stage.name for stage in value.runtime.stages]
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(names, ["load", "verify", "policy", "project", "complete"])

    def test_registry_and_packet_totals_are_additive(self):
        value = self.build_federation()
        self.assertEqual(value.total_packet_count, sum(entry.packet_count for entry in value.entries))
        self.assertEqual(value.ready_packet_count, sum(entry.ready_packet_count for entry in value.entries))
        self.assertEqual(value.held_packet_count, sum(entry.held_packet_count for entry in value.entries))
        self.assertEqual(value.blocked_packet_count, sum(entry.blocked_packet_count for entry in value.entries))
        self.assertEqual(value.accepted_packet_count, sum(entry.accepted_packet_count for entry in value.entries))
        self.assertEqual(value.release_ready_packet_count, sum(entry.release_ready_packet_count for entry in value.entries))

    def test_registry_and_packet_state_counts_are_additive(self):
        value = self.build_federation()
        self.assertEqual(value.registry_count, value.ready_registry_count + value.held_registry_count + value.blocked_registry_count)
        self.assertEqual(value.total_packet_count, value.ready_packet_count + value.held_packet_count + value.blocked_packet_count)
        self.assertEqual(value.accepted_registry_count, value.ready_registry_count + value.held_registry_count + value.blocked_registry_count)
        self.assertEqual(value.release_ready_registry_count, value.ready_registry_count)

    def test_federation_policy_and_runtime_are_replaceable_receipts(self):
        first = self.build_federation()
        policy = federation.default_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_policy(policy_id="policy:replaceable")
        second = federation.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation((self.build_named_registry("registry:a"), self.build_named_registry("registry:b")), federation_id="federation:replaceable", policy=policy)
        self.assertEqual(first.registry_count, second.registry_count)
        self.assertEqual(first.total_packet_count, second.total_packet_count)
        self.assertNotEqual(first.policy_address, second.policy_address)
        self.assertNotEqual(first.runtime_address, second.runtime_address)

    def test_public_schema_state_values_match_runtime_states(self):
        schema = federation.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_schema()
        runtime_schema = federation.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_runtime_schema()
        self.assertEqual(schema["state_values"], ["ready", "held", "blocked", "empty"])
        self.assertEqual(runtime_schema["states"], ["ready", "held", "blocked"])
        self.assertEqual(runtime_schema["stages"], ["load", "verify", "policy", "project", "complete"])

    def test_capability_surface_declares_all_transport_guarantees(self):
        capabilities = federation.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_capabilities()
        expected = {
            "deterministic_order",
            "unique_registry_addresses",
            "conserved_registry_and_packet_rollups",
            "independent_verification",
            "policy_governed_runtime",
            "exact_byte_persistence",
            "canonical_json_enforcement",
            "symlink_rejection",
            "bounded_queries",
            "json_csv_markdown_exports",
            "offline_reload",
            "source_payloads_required_for_reload",
            "supports_ready_held_blocked_and_empty_states",
        }
        self.assertEqual(expected, set(capabilities) - {"version", "boundary"})

    def test_query_capability_surface_declares_all_filters(self):
        schema = federation.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_query_schema()
        capabilities = federation.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_query_capabilities()
        self.assertEqual(schema["filters"], ["state", "accepted", "release_ready", "text", "offset", "limit"])
        self.assertTrue(capabilities["state_filter"])
        self.assertTrue(capabilities["acceptance_filter"])
        self.assertTrue(capabilities["readiness_filter"])
        self.assertTrue(capabilities["text_filter"])
        self.assertTrue(capabilities["pagination"])

    def test_persistence_round_trip_is_repeatable_for_same_value(self):
        value = self.build_federation()
        with tempfile.TemporaryDirectory() as root:
            first = self.write_federation(value, Path(root) / "first")
            second = self.write_federation(value, Path(root) / "second")
            first_bytes = {path.name: path.read_bytes() for path in first.iterdir()}
            second_bytes = {path.name: path.read_bytes() for path in second.iterdir()}
            self.assertEqual(first_bytes, second_bytes)

    def test_real_downloaded_data_is_represented_only_by_addresses(self):
        source = self.real_packet()
        if not source.is_dir():
            self.skipTest("retained downloaded packet fixture is not installed")
        with tempfile.TemporaryDirectory() as root:
            history_value = history.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_from_directories(source, source, history_id="history:address-only-real")
            history_directory = self.write_history(root, history_value, "history")
            packet_value = packet.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_from_history_directories((history_directory, history_directory), observation_ids=("address-only-a", "address-only-b"), packet_id="packet:address-only")
            registry_value = registry.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry((packet_value,), registry_id="registry:address-only")
            value = federation.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation((registry_value,), federation_id="federation:address-only")
            output = json.dumps(value.to_dict()).casefold()
            self.assertNotIn(str(source).casefold(), output)
            self.assertNotIn("source_path", output)
            self.assertIn("content_address", output)


if __name__ == "__main__":
    unittest.main()
