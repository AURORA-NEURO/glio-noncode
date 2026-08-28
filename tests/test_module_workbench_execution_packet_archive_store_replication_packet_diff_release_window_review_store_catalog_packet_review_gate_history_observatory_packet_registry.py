# ruff: noqa: E501

from __future__ import annotations

import json
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from http.client import HTTPConnection
from io import StringIO
from pathlib import Path
from urllib.parse import urlencode

import glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history as history
import glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet as packet
import glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry as registry
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.serialization import canonical_bytes
from tests.test_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory import (
    ObservatoryFixture,
)


class RegistryFixture(ObservatoryFixture):
    def closure_packet(
        self,
        packet_id: str,
        decisions: tuple[str, ...] = ("promote", "promote"),
    ):
        return packet.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet(
            self.build(decisions), packet_id=packet_id
        )

    def build_registry(self, packet_ids=("packet:a", "packet:b")):
        return registry.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
            tuple(self.closure_packet(packet_id) for packet_id in packet_ids),
            registry_id="registry:fixture",
        )

    @staticmethod
    def http_json(server, path: str, params=None):
        params = params or {}
        query = []
        for key, value in params.items():
            if isinstance(value, tuple):
                query.extend((key, item) for item in value)
            else:
                query.append((key, value))
        connection = HTTPConnection("127.0.0.1", server.server_address[1], timeout=15)
        connection.request("GET", path + ("?" + urlencode(query) if query else ""))
        response = connection.getresponse()
        content_type = response.getheader("Content-Type", "")
        body = response.read().decode("utf-8")
        connection.close()
        return response.status, content_type, json.loads(body)

    @staticmethod
    def http_text(server, path: str, params=None):
        params = params or {}
        query = []
        for key, value in params.items():
            if isinstance(value, tuple):
                query.extend((key, item) for item in value)
            else:
                query.append((key, value))
        connection = HTTPConnection("127.0.0.1", server.server_address[1], timeout=15)
        connection.request("GET", path + ("?" + urlencode(query) if query else ""))
        response = connection.getresponse()
        content_type = response.getheader("Content-Type", "")
        body = response.read().decode("utf-8")
        connection.close()
        return response.status, content_type, body


class RegistryCoreTests(RegistryFixture):
    def test_ready_registry_conserves_two_packets(self):
        value = self.build_registry()
        self.assertTrue(value.accepted)
        self.assertTrue(value.release_ready)
        self.assertEqual(value.state, "ready")
        self.assertEqual(value.packet_count, 2)
        self.assertEqual(value.ready_count, 2)
        self.assertEqual(value.held_count, 0)
        self.assertEqual(value.blocked_count, 0)
        self.assertEqual(value.accepted_count, 2)
        self.assertEqual(value.release_ready_count, 2)
        self.assertEqual([item.ordinal for item in value.entries], [0, 1])
        self.assertEqual([item.packet_id for item in value.entries], ["packet:a", "packet:b"])

    def test_registry_sorting_is_input_order_independent(self):
        first = self.build_registry(("packet:b", "packet:a"))
        second = self.build_registry(("packet:a", "packet:b"))
        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(
            [item.content_address for item in first.entries],
            [item.content_address for item in second.entries],
        )

    def test_registry_verification_is_independent_and_conserved(self):
        value = self.build_registry()
        receipt = registry.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
            value
        )
        self.assertTrue(receipt.accepted)
        self.assertEqual(receipt.failed_count, 0)
        self.assertEqual(receipt.check_count, 13)
        self.assertEqual(
            [item.kind for item in receipt.checks],
            [
                "registry-address",
                "entry-count",
                "entry-order",
                "packet-id-uniqueness",
                "packet-address-uniqueness",
                "state-conservation",
                "acceptance-conservation",
                "readiness-conservation",
                "state-projection",
                "release-projection",
                "entry-addresses",
                "packet-links",
                "public-boundary",
            ],
        )

    def test_registry_addresses_and_entry_addresses_are_repeatable(self):
        first = self.build_registry()
        second = self.build_registry()
        self.assertEqual(
            registry.address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
                first
            ),
            first.content_address,
        )
        self.assertEqual(first.content_address, second.content_address)
        for left, right in zip(first.entries, second.entries, strict=True):
            self.assertEqual(left.content_address, right.content_address)
            self.assertEqual(
                registry.address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_entry(
                    left
                ),
                left.content_address,
            )

    def test_held_registry_preserves_nonready_evidence(self):
        ready = self.closure_packet("packet:ready")
        held = packet.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet(
            self.build(("hold", "hold")),
            policy=packet.default_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime_policy(
                policy_id="policy:held",
                require_latest_release_ready=False,
            ),
            packet_id="packet:held",
        )
        value = registry.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
            (ready, held), registry_id="registry:held"
        )
        self.assertTrue(value.accepted)
        self.assertFalse(value.release_ready)
        self.assertEqual(value.state, "held")
        self.assertEqual(value.ready_count, 1)
        self.assertEqual(value.held_count, 1)
        self.assertEqual(value.blocked_count, 0)

    def test_blocked_registry_is_distinct_from_held_registry(self):
        ready = self.closure_packet("packet:ready")
        blocked = packet.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet(
            self.build(("promote", "hold")), packet_id="packet:blocked"
        )
        value = registry.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
            (ready, blocked), registry_id="registry:blocked"
        )
        self.assertTrue(value.accepted)
        self.assertFalse(value.release_ready)
        self.assertEqual(value.state, "blocked")
        self.assertEqual(value.blocked_count, 1)

    def test_empty_registry_is_explicit(self):
        value = registry.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
            (), registry_id="registry:empty"
        )
        self.assertTrue(value.accepted)
        self.assertFalse(value.release_ready)
        self.assertEqual(value.state, "empty")
        self.assertEqual(value.packet_count, 0)
        self.assertTrue(
            registry.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
                value
            ).accepted
        )

    def test_duplicate_packet_ids_are_rejected(self):
        first = self.closure_packet("packet:duplicate")
        second = self.closure_packet("packet:duplicate")
        with self.assertRaises(ValidationError):
            registry.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
                (first, second)
            )

    def test_duplicate_packet_addresses_are_rejected(self):
        first = self.closure_packet("packet:same")
        second = self.closure_packet("packet:same")
        second.packet_id = "packet:other"
        with self.assertRaises(ValidationError):
            registry.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
                (first, second)
            )

    def test_untyped_or_unaccepted_packets_are_rejected(self):
        with self.assertRaises(ValidationError):
            registry.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
                (object(),)
            )
        value = self.closure_packet("packet:tampered")
        value.content_address = "tampered:packet"
        with self.assertRaises(ValidationError):
            registry.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
                (value,)
            )

    def test_registry_mapping_round_trip(self):
        value = self.build_registry()
        restored = registry.registry_from_mapping(value.to_dict())
        self.assertEqual(restored.to_dict(), value.to_dict())
        self.assertEqual(restored.content_address, value.content_address)
        entry = registry.registry_entry_from_mapping(value.entries[0].to_dict())
        self.assertEqual(entry.to_dict(), value.entries[0].to_dict())
        verification = registry.registry_verification_from_mapping(value.verification.to_dict())
        self.assertEqual(verification.to_dict(), value.verification.to_dict())

    def test_registry_mapping_rejects_nonobjects(self):
        for converter in (
            registry.registry_from_mapping,
            registry.registry_entry_from_mapping,
            registry.registry_check_from_mapping,
            registry.registry_verification_from_mapping,
        ):
            with self.assertRaises(ValidationError):
                converter([])

    def test_registry_schema_and_capabilities_are_identity_free(self):
        schema = registry.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_schema()
        capabilities = registry.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_capabilities()
        query_schema = registry.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_query_schema()
        verification_schema = registry.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_verification_schema()
        self.assertEqual(
            schema["exact_files"],
            ["manifest.json", "registry.json", "packets.json", "verification.json"],
        )
        self.assertEqual(schema["maximum_packets"], 256)
        self.assertTrue(capabilities["unique_packet_addresses"])
        self.assertEqual(
            query_schema["resources"], ["summary", "entries", "packets", "verification", "checks"]
        )
        self.assertTrue(verification_schema["independent"])
        self.assertNotIn("agent", json.dumps(schema).casefold())
        self.assertNotIn("model", json.dumps(capabilities).casefold())


class RegistryQueryTests(RegistryFixture):
    def setUp(self):
        self.value = self.build_registry()

    def test_all_query_resources_have_expected_totals(self):
        expected = {"summary": 1, "entries": 2, "packets": 2, "verification": 1, "checks": 13}
        for resource, total in expected.items():
            with self.subTest(resource=resource):
                result = registry.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
                    self.value, resource=resource
                )
                self.assertEqual(result.total, total)
                self.assertEqual(len(result.items), total)
                self.assertTrue(
                    registry.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_query(
                        result
                    )
                )

    def test_state_accepted_and_ready_filters(self):
        ready = registry.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
            self.value, resource="entries", state="ready", accepted=True, release_ready=True
        )
        self.assertEqual(ready.total, 2)
        self.assertTrue(all(item["state"] == "ready" for item in ready.items))
        checks = registry.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
            self.value, resource="checks"
        )
        self.assertEqual(checks.total, 13)

    def test_text_filter_and_pagination(self):
        result = registry.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
            self.value, resource="entries", text="packet:b", offset=0, limit=1
        )
        self.assertEqual(result.total, 1)
        self.assertEqual(len(result.items), 1)
        self.assertEqual(result.items[0]["packet_id"], "packet:b")
        self.assertEqual(result.offset, 0)
        self.assertEqual(result.limit, 1)

    def test_empty_page_keeps_total(self):
        result = registry.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
            self.value, resource="entries", offset=2, limit=5
        )
        self.assertEqual(result.total, 2)
        self.assertEqual(result.items, ())

    def test_invalid_query_is_rejected(self):
        with self.assertRaises(ValidationError):
            registry.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
                self.value, resource="nope"
            )
        with self.assertRaises(ValidationError):
            registry.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
                self.value, resource="entries", state="nope"
            )
        with self.assertRaises(ValidationError):
            registry.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
                self.value, resource="entries", limit=0
            )

    def test_query_exports_are_deterministic(self):
        result = registry.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
            self.value, resource="entries"
        )
        self.assertEqual(
            json.loads(
                registry.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_query_json(
                    result
                )
            ),
            result.to_dict(),
        )
        self.assertIn(
            "packet_id",
            registry.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_query_csv(
                result
            ),
        )
        self.assertIn(
            "# Observatory packet registry query",
            registry.render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_query_markdown(
                result
            ),
        )

    def test_registry_exports_are_deterministic(self):
        self.assertEqual(
            json.loads(
                registry.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_json(
                    self.value
                )
            ),
            self.value.to_dict(),
        )
        self.assertIn(
            "packet_address",
            registry.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_csv(
                self.value
            ),
        )
        self.assertIn(
            "# Observatory packet registry",
            registry.render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_markdown(
                self.value
            ),
        )


class RegistryPersistenceTests(RegistryFixture):
    def test_exact_four_file_round_trip(self):
        value = self.build_registry()
        with tempfile.TemporaryDirectory() as root:
            destination = registry.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
                value, Path(root) / "registry"
            )
            self.assertEqual(
                {item.name for item in destination.iterdir()},
                {"manifest.json", "registry.json", "packets.json", "verification.json"},
            )
            loaded = registry.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
                destination
            )
            self.assertEqual(loaded.to_dict(), value.to_dict())
            self.assertEqual(loaded.content_address, value.content_address)
            self.assertTrue(
                registry.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
                    loaded
                ).accepted
            )

    def test_overwrite_requires_explicit_flag(self):
        value = self.build_registry()
        with tempfile.TemporaryDirectory() as root:
            destination = registry.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
                value, Path(root) / "registry"
            )
            with self.assertRaises(ValidationError):
                registry.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
                    value, destination
                )
            registry.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
                value, destination, overwrite=True
            )

    def test_extra_and_missing_files_are_rejected(self):
        value = self.build_registry()
        with tempfile.TemporaryDirectory() as root:
            destination = registry.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
                value, Path(root) / "registry"
            )
            (destination / "extra.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(ValidationError):
                registry.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
                    destination
                )
            (destination / "extra.json").unlink()
            (destination / "manifest.json").unlink()
            with self.assertRaises(ValidationError):
                registry.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
                    destination
                )

    def test_noncanonical_document_is_rejected(self):
        value = self.build_registry()
        with tempfile.TemporaryDirectory() as root:
            destination = registry.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
                value, Path(root) / "registry"
            )
            (destination / "registry.json").write_bytes(b'{ "wrong": true }\n')
            with self.assertRaises(ValidationError):
                registry.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
                    destination
                )

    def test_manifest_address_and_receipts_are_verified(self):
        value = self.build_registry()
        with tempfile.TemporaryDirectory() as root:
            destination = registry.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
                value, Path(root) / "registry"
            )
            manifest_path = destination / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["manifest_address"] = "tampered:manifest"
            manifest_path.write_bytes(canonical_bytes(manifest))
            with self.assertRaises(ValidationError):
                registry.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
                    destination
                )

    def test_each_persisted_document_tamper_is_rejected(self):
        value = self.build_registry()
        changes = {
            "registry.json": "registry_id",
            "packets.json": "packets",
            "verification.json": "registry_address",
        }
        for file_name, key in changes.items():
            with self.subTest(file_name=file_name):
                with tempfile.TemporaryDirectory() as root:
                    destination = registry.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
                        value, Path(root) / "registry"
                    )
                    path = destination / file_name
                    document = json.loads(path.read_text(encoding="utf-8"))
                    if file_name == "packets.json":
                        document[key][0]["packet_id"] += ":tampered"
                    else:
                        document[key] = str(document[key]) + ":tampered"
                    path.write_bytes(canonical_bytes(document))
                    with self.assertRaises(ValidationError):
                        registry.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
                            destination
                        )

    def test_file_and_directory_symlinks_are_rejected(self):
        value = self.build_registry()
        with tempfile.TemporaryDirectory() as root:
            destination = registry.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
                value, Path(root) / "registry"
            )
            with self.assertRaises(ValidationError):
                registry.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
                    destination / "registry.json"
                )
            try:
                link = Path(root) / "link"
                link.symlink_to(destination, target_is_directory=True)
            except (OSError, NotImplementedError):
                return
            with self.assertRaises(ValidationError):
                registry.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
                    link
                )

    def test_mutated_registry_receipt_cannot_be_written(self):
        value = self.build_registry()
        value.content_address = "stale:registry"
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValidationError):
                registry.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
                    value, Path(root) / "registry"
                )

    def test_directory_builder_loads_multiple_packets(self):
        with tempfile.TemporaryDirectory() as root:
            first_packet = self.closure_packet("packet:directory-a")
            second_packet = self.closure_packet("packet:directory-b")
            first = packet.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet(
                first_packet, Path(root) / "packet-a"
            )
            second = packet.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet(
                second_packet, Path(root) / "packet-b"
            )
            value = registry.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_from_directories(
                (first, second), registry_id="registry:directories"
            )
            self.assertEqual(value.packet_count, 2)
            self.assertEqual(value.registry_id, "registry:directories")


class RegistryCliTests(RegistryFixture):
    base = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-packet-registry"

    def cli_json(self, arguments):
        output = StringIO()
        with redirect_stdout(output):
            status = main(arguments)
        return status, json.loads(output.getvalue())

    def test_cli_contract_commands(self):
        for suffix in (
            "-schema",
            "-capabilities",
            "-query-schema",
            "-query-capabilities",
            "-verification-schema",
            "-verification-capabilities",
        ):
            status, value = self.cli_json([self.base + suffix])
            self.assertEqual(status, 0, suffix)
            self.assertTrue(value, suffix)

    def test_cli_build_query_and_verify(self):
        with tempfile.TemporaryDirectory() as root:
            first_packet = self.closure_packet("packet:cli-a")
            second_packet = self.closure_packet("packet:cli-b")
            first = packet.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet(
                first_packet, Path(root) / "packet-a"
            )
            second = packet.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet(
                second_packet, Path(root) / "packet-b"
            )
            destination = Path(root) / "registry"
            status, summary = self.cli_json(
                [
                    self.base,
                    "--packet-directory",
                    str(first),
                    "--packet-directory",
                    str(second),
                    "--registry-id",
                    "registry:cli",
                    "--destination",
                    str(destination),
                    "--format",
                    "summary",
                ]
            )
            self.assertEqual(status, 0)
            self.assertEqual(summary["packet_count"], 2)
            status, query = self.cli_json(
                [
                    self.base + "-query",
                    "--input",
                    str(destination),
                    "--resource",
                    "entries",
                    "--state",
                    "ready",
                ]
            )
            self.assertEqual(status, 0)
            self.assertEqual(query["total"], 2)
            status, verification = self.cli_json(
                [self.base + "-verify", "--input", str(destination)]
            )
            self.assertEqual(status, 0)
            self.assertTrue(verification["accepted"])

    def test_cli_exports_are_nonempty(self):
        with tempfile.TemporaryDirectory() as root:
            first = packet.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet(
                self.closure_packet("packet:cli"), Path(root) / "packet"
            )
            for output_format, marker in (
                ("json", '"registry_id"'),
                ("csv", "packet_id"),
                ("markdown", "# Observatory packet registry"),
            ):
                output = StringIO()
                with redirect_stdout(output):
                    status = main(
                        [self.base, "--packet-directory", str(first), "--format", output_format]
                    )
                self.assertEqual(status, 0)
                self.assertIn(marker, output.getvalue())


class RegistryApiTests(RegistryFixture):
    base = "/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/observatory/packet/registry"

    def test_api_contract_resources(self):
        server = create_server(
            "127.0.0.1", 0, Path(tempfile.gettempdir()) / "glio-noncode-api-registry"
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            for suffix in (
                "/schema",
                "/capabilities",
                "/query/schema",
                "/query/capabilities",
                "/verification/schema",
                "/verification/capabilities",
            ):
                status, content_type, value = self.http_json(server, self.base + suffix)
                self.assertEqual(status, 200, suffix)
                self.assertIn("application/json", content_type)
                self.assertTrue(value, suffix)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_api_build_load_query_and_verify(self):
        with tempfile.TemporaryDirectory() as root:
            first = packet.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet(
                self.closure_packet("packet:api-a"), Path(root) / "packet-a"
            )
            second = packet.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet(
                self.closure_packet("packet:api-b"), Path(root) / "packet-b"
            )
            registry_directory = Path(root) / "registry"
            value = registry.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_from_directories(
                (first, second)
            )
            registry.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
                value, registry_directory
            )
            server = create_server("127.0.0.1", 0, Path(root) / "api-data")
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                status, _, summary = self.http_json(
                    server, self.base, {"packet_directory": (str(first), str(second))}
                )
                self.assertEqual(status, 200)
                self.assertEqual(summary["packet_count"], 2)
                status, _, query = self.http_json(
                    server,
                    self.base + "/query",
                    {"input": str(registry_directory), "resource": "entries", "limit": "1"},
                )
                self.assertEqual(status, 200)
                self.assertEqual(query["total"], 2)
                self.assertEqual(len(query["items"]), 1)
                status, _, verification = self.http_json(
                    server, self.base + "/verify", {"input": str(registry_directory)}
                )
                self.assertEqual(status, 200)
                self.assertTrue(verification["accepted"])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_api_csv_and_markdown_are_text_responses(self):
        with tempfile.TemporaryDirectory() as root:
            first = packet.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet(
                self.closure_packet("packet:api-format"), Path(root) / "packet"
            )
            server = create_server("127.0.0.1", 0, Path(root) / "api-data")
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                for output_format, marker in (
                    ("csv", "packet_id"),
                    ("markdown", "# Observatory packet registry"),
                ):
                    status, content_type, body = self.http_text(
                        server, self.base, {"packet_directory": str(first), "format": output_format}
                    )
                    self.assertEqual(status, 200)
                    self.assertTrue(content_type)
                    self.assertIn(marker, body)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


class RegistryRealDataTests(RegistryFixture):
    def test_real_downloaded_packet_handoffs_form_a_registry(self):
        source = self.real_packet()
        if not source.is_dir():
            self.skipTest("retained downloaded packet fixture is not installed")
        with tempfile.TemporaryDirectory() as root:
            history_value = history.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_from_directories(
                source, source, history_id="history:registry-real"
            )
            history_directory = self.write_history(root, history_value, "real-history")
            first = packet.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_from_history_directories(
                (history_directory, history_directory),
                observation_ids=("real-baseline", "real-rerun"),
                packet_id="packet:real-a",
            )
            second = packet.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_from_history_directories(
                (history_directory, history_directory),
                observation_ids=("real-baseline-2", "real-rerun-2"),
                packet_id="packet:real-b",
            )
            value = registry.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
                (first, second), registry_id="registry:real"
            )
            destination = registry.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
                value, Path(root) / "real-registry"
            )
            loaded = registry.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry(
                destination
            )
            self.assertTrue(loaded.accepted)
            self.assertTrue(loaded.release_ready)
            self.assertEqual(loaded.packet_count, 2)
            self.assertEqual(loaded.verification.failed_count, 0)
            self.assertEqual(
                [item.packet_id for item in loaded.entries], ["packet:real-a", "packet:real-b"]
            )


if __name__ == "__main__":
    unittest.main()
