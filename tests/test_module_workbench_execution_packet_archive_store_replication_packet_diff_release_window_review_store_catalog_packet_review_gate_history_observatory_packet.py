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
import glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime as runtime
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.serialization import canonical_bytes
from tests.test_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory import (
    ObservatoryFixture,
)


class PacketFixture(ObservatoryFixture):
    packet_id = "packet:fixture"

    def build_packet(self, decisions: tuple[str, ...] = ("promote", "promote")):
        return packet.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet(
            self.build(decisions), packet_id=self.packet_id
        )

    def build_held_packet(self):
        observatory_value = self.build(("promote", "hold"))
        policy = runtime.default_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime_policy(
            allow_mixed_state=True,
            maximum_regressions=1,
            require_latest_release_ready=False,
        )
        return packet.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet(
            observatory_value, policy=policy, packet_id="packet:held"
        )

    def write_observatory_and_runtime(self, root: str | Path, decisions=("promote", "promote")):
        root = Path(root)
        observatory_value = self.build(decisions)
        report = runtime.run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_catalog_packet_review_gate_history_observatory_runtime(
            observatory_value, runtime_id="runtime:packet-fixture"
        )
        observatory_directory = root / "observatory"
        runtime_directory = root / "runtime"
        from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory import (
            write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory,
        )

        write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory(
            observatory_value, observatory_directory
        )
        runtime.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime(
            report, runtime_directory
        )
        return observatory_directory, runtime_directory

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


class PacketCoreTests(PacketFixture):
    def test_ready_packet_projects_all_components(self):
        value = self.build_packet()
        self.assertTrue(value.accepted)
        self.assertTrue(value.release_ready)
        self.assertEqual(value.state, "ready")
        self.assertEqual(value.artifact_count, 4)
        self.assertEqual(
            [item.kind for item in value.artifacts],
            ["observatory", "verification", "policy", "runtime"],
        )
        self.assertEqual(value.observatory.content_address, value.observatory_address)
        self.assertEqual(value.verification.content_address, value.verification_address)
        self.assertEqual(value.policy.content_address, value.policy_address)
        self.assertEqual(value.runtime.content_address, value.runtime_address)

    def test_packet_verification_recomputes_without_embedded_receipt(self):
        value = self.build_packet()
        receipt = packet.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet(
            value
        )
        self.assertTrue(receipt.accepted)
        self.assertEqual(receipt.failed_count, 0)
        self.assertEqual(receipt.check_count, 14)
        self.assertEqual(
            [item.kind for item in receipt.checks],
            [
                "packet-address",
                "artifact-count",
                "artifact-order",
                "artifact-files",
                "observatory-link",
                "observatory-verification",
                "policy-link",
                "runtime-link",
                "runtime-observatory-link",
                "runtime-policy-link",
                "runtime-replay",
                "state-projection",
                "release-projection",
                "public-boundary",
            ],
        )

    def test_packet_address_is_stable_and_acyclic(self):
        first = self.build_packet()
        second = self.build_packet()
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(first.verification.content_address, second.verification.content_address)
        self.assertEqual(
            packet.address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet(
                first
            ),
            first.content_address,
        )

    def test_packet_is_path_free_and_attribution_free(self):
        value = self.build_packet()
        projection = json.dumps(value.to_dict(), sort_keys=True)
        for forbidden in (
            "C:\\",
            "agent",
            "assistant",
            "author",
            "email",
            "language",
            "model",
            "private",
            "secret",
            "token",
            "user",
        ):
            self.assertNotIn(forbidden, projection.casefold())

    def test_held_runtime_is_transport_valid_but_not_release_ready(self):
        value = self.build_held_packet()
        self.assertTrue(value.accepted)
        self.assertFalse(value.release_ready)
        self.assertEqual(value.state, "held")
        self.assertTrue(
            packet.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet(
                value
            ).accepted
        )

    def test_blocked_runtime_is_preserved_as_packet_evidence(self):
        value = packet.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet(
            self.build(("promote", "hold")), packet_id="packet:blocked"
        )
        self.assertTrue(value.accepted)
        self.assertFalse(value.release_ready)
        self.assertEqual(value.state, "blocked")
        self.assertTrue(
            packet.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet(
                value
            ).accepted
        )

    def test_builder_rejects_untyped_observatory(self):
        with self.assertRaises(ValidationError):
            packet.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet(
                object()
            )

    def test_builder_rejects_mismatched_runtime_links(self):
        value = self.build_packet()
        other = self.build_held_packet()
        with self.assertRaises(ValidationError):
            packet.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet(
                value.observatory, runtime_report=other.runtime
            )

    def test_mapping_round_trips_packet_and_receipt(self):
        value = self.build_packet()
        restored = packet.packet_from_mapping(value.to_dict())
        self.assertEqual(restored.to_dict(), value.to_dict())
        self.assertEqual(restored.content_address, value.content_address)
        verification = packet.packet_verification_from_mapping(value.verification.to_dict())
        self.assertEqual(verification.to_dict(), value.verification.to_dict())
        policy = packet.packet_policy_from_mapping(value.policy.to_dict())
        self.assertEqual(policy.to_dict(), value.policy.to_dict())

    def test_mapping_rejects_nonobjects(self):
        for converter in (
            packet.packet_from_mapping,
            packet.packet_verification_from_mapping,
            packet.packet_policy_from_mapping,
        ):
            with self.assertRaises(ValidationError):
                converter([])

    def test_schema_and_capabilities_are_detailed(self):
        schema = packet.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_schema()
        capabilities = packet.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_capabilities()
        query_schema = packet.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_query_schema()
        verification_schema = packet.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_verification_schema()
        self.assertEqual(
            schema["exact_files"],
            [
                "manifest.json",
                "observatory.json",
                "verification.json",
                "policy.json",
                "runtime.json",
            ],
        )
        self.assertEqual(capabilities["component_count"], 4)
        self.assertTrue(capabilities["atomic_write"])
        self.assertTrue(capabilities["independent_verification"])
        self.assertEqual(
            query_schema["resources"],
            [
                "summary",
                "artifacts",
                "verification",
                "observations",
                "transitions",
                "stages",
                "policy-checks",
            ],
        )
        self.assertTrue(verification_schema["independent"])
        self.assertNotIn("agent", json.dumps(capabilities).casefold())


class PacketQueryTests(PacketFixture):
    def setUp(self):
        self.value = self.build_packet()

    def test_all_query_resources_are_bounded_and_addressed(self):
        expected = {
            "summary": 1,
            "artifacts": 4,
            "verification": 1,
            "observations": 2,
            "transitions": 1,
            "stages": 5,
            "policy-checks": 8,
        }
        for resource, total in expected.items():
            result = packet.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet(
                self.value, resource=resource
            )
            self.assertEqual(result.total, total, resource)
            self.assertEqual(len(result.items), total, resource)
            self.assertTrue(
                packet.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_query(
                    result
                ),
                resource,
            )

    def test_artifact_kind_filter(self):
        result = packet.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet(
            self.value, resource="artifacts", kind="runtime"
        )
        self.assertEqual(result.total, 1)
        self.assertEqual(result.items[0]["kind"], "runtime")

    def test_pass_filter_targets_policy_checks(self):
        result = packet.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet(
            self.value, resource="policy-checks", passed=True
        )
        self.assertEqual(result.total, 8)
        self.assertTrue(all(item["passed"] for item in result.items))

    def test_text_filter_and_pagination(self):
        result = packet.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet(
            self.value, resource="stages", text="independent", offset=0, limit=1
        )
        self.assertEqual(result.total, 1)
        self.assertEqual(len(result.items), 1)
        self.assertEqual(result.items[0]["name"], "verify")
        self.assertEqual(result.offset, 0)
        self.assertEqual(result.limit, 1)

    def test_query_rejects_invalid_filters(self):
        with self.assertRaises(ValidationError):
            packet.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet(
                self.value, resource="artifacts", kind="not-a-kind"
            )
        with self.assertRaises(ValidationError):
            packet.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet(
                self.value, resource="summary", limit=0
            )
        with self.assertRaises(ValidationError):
            packet.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet(
                self.value, resource="summary", offset=-1
            )

    def test_query_exports_round_trip(self):
        result = packet.query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet(
            self.value, resource="transitions"
        )
        self.assertEqual(
            json.loads(
                packet.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_query_json(
                    result
                )
            ),
            result.to_dict(),
        )
        self.assertIn(
            "kind",
            packet.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_query_csv(
                result
            ),
        )
        self.assertIn(
            "Packet-review gate history observatory packet query",
            packet.render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_query_markdown(
                result
            ),
        )

    def test_packet_exports_are_deterministic(self):
        self.assertEqual(
            json.loads(
                packet.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_json(
                    self.value
                )
            ),
            self.value.to_dict(),
        )
        self.assertIn(
            "verification.json",
            packet.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_csv(
                self.value
            ),
        )
        self.assertIn(
            "# Packet-review gate history observatory packet",
            packet.render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_markdown(
                self.value
            ),
        )


class PacketPersistenceTests(PacketFixture):
    def test_exact_five_file_round_trip(self):
        value = self.build_packet()
        with tempfile.TemporaryDirectory() as root:
            destination = packet.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet(
                value, Path(root) / "packet"
            )
            self.assertEqual(
                {item.name for item in destination.iterdir()},
                {
                    "manifest.json",
                    "observatory.json",
                    "verification.json",
                    "policy.json",
                    "runtime.json",
                },
            )
            loaded = packet.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet(
                destination
            )
            self.assertEqual(loaded.to_dict(), value.to_dict())
            self.assertEqual(loaded.content_address, value.content_address)
            self.assertTrue(
                packet.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet(
                    loaded
                ).accepted
            )

    def test_overwrite_requires_explicit_flag(self):
        value = self.build_packet()
        with tempfile.TemporaryDirectory() as root:
            destination = packet.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet(
                value, Path(root) / "packet"
            )
            with self.assertRaises(ValidationError):
                packet.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet(
                    value, destination
                )
            packet.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet(
                value, destination, overwrite=True
            )

    def test_extra_file_and_missing_file_are_rejected(self):
        value = self.build_packet()
        with tempfile.TemporaryDirectory() as root:
            destination = packet.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet(
                value, Path(root) / "packet"
            )
            (destination / "extra.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(ValidationError):
                packet.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet(
                    destination
                )
            (destination / "extra.json").unlink()
            (destination / "manifest.json").unlink()
            with self.assertRaises(ValidationError):
                packet.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet(
                    destination
                )

    def test_noncanonical_manifest_is_rejected(self):
        value = self.build_packet()
        with tempfile.TemporaryDirectory() as root:
            destination = packet.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet(
                value, Path(root) / "packet"
            )
            manifest = destination / "manifest.json"
            manifest.write_bytes(b'{ "packet_id": "wrong" }\n')
            with self.assertRaises(ValidationError):
                packet.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet(
                    destination
                )

    def test_manifest_address_tamper_is_rejected(self):
        value = self.build_packet()
        with tempfile.TemporaryDirectory() as root:
            destination = packet.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet(
                value, Path(root) / "packet"
            )
            manifest_path = destination / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["manifest_address"] = "tampered:manifest"
            manifest_path.write_bytes(canonical_bytes(manifest))
            with self.assertRaises(ValidationError):
                packet.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet(
                    destination
                )

    def test_manifest_artifact_receipt_tamper_is_rejected(self):
        value = self.build_packet()
        with tempfile.TemporaryDirectory() as root:
            destination = packet.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet(
                value, Path(root) / "packet"
            )
            manifest_path = destination / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["artifacts"][0]["byte_count"] += 1
            manifest["artifact_files"][0]["byte_count"] += 1
            manifest_body = {
                key: item for key, item in manifest.items() if key != "manifest_address"
            }
            from glio_noncode.serialization import content_hash

            manifest["manifest_address"] = content_hash(
                manifest_body,
                prefix=packet.MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_PACKET_PREFIX
                + "-manifest",
            )
            manifest_path.write_bytes(canonical_bytes(manifest))
            with self.assertRaises(ValidationError):
                packet.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet(
                    destination
                )

    def test_each_nested_document_tamper_is_rejected(self):
        value = self.build_packet()
        changes = {
            "observatory.json": "observatory_id",
            "verification.json": "packet_address",
            "policy.json": "policy_id",
            "runtime.json": "runtime_id",
        }
        for file_name, key in changes.items():
            with self.subTest(file_name=file_name):
                with tempfile.TemporaryDirectory() as root:
                    destination = packet.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet(
                        value, Path(root) / "packet"
                    )
                    path = destination / file_name
                    document = json.loads(path.read_text(encoding="utf-8"))
                    document[key] = str(document[key]) + ":tampered"
                    path.write_bytes(canonical_bytes(document))
                    with self.assertRaises(ValidationError):
                        packet.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet(
                            destination
                        )

    def test_file_and_directory_symlink_inputs_are_rejected(self):
        value = self.build_packet()
        with tempfile.TemporaryDirectory() as root:
            destination = packet.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet(
                value, Path(root) / "packet"
            )
            with self.assertRaises(ValidationError):
                packet.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet(
                    destination / "runtime.json"
                )
            try:
                link = Path(root) / "packet-link"
                link.symlink_to(destination, target_is_directory=True)
            except (OSError, NotImplementedError):
                return
            with self.assertRaises(ValidationError):
                packet.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet(
                    link
                )

    def test_writer_rejects_stale_artifact_receipt(self):
        value = self.build_packet()
        value.artifacts[0].byte_address = "stale:address"
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValidationError):
                packet.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet(
                    value, Path(root) / "packet"
                )

    def test_writer_is_atomic_on_destination_parent(self):
        value = self.build_packet()
        with tempfile.TemporaryDirectory() as root:
            parent = Path(root) / "nested" / "handoffs"
            destination = packet.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet(
                value, parent / "packet"
            )
            self.assertTrue(destination.is_dir())
            self.assertFalse(any(item.name.startswith(".packet-") for item in parent.iterdir()))

    def test_directory_builder_uses_persisted_observatory_and_runtime(self):
        with tempfile.TemporaryDirectory() as root:
            observatory_directory, runtime_directory = self.write_observatory_and_runtime(root)
            value = packet.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_from_observatory_directory(
                observatory_directory,
                runtime_directory=runtime_directory,
                packet_id="packet:directory",
            )
            self.assertEqual(value.packet_id, "packet:directory")
            self.assertTrue(value.release_ready)
            self.assertTrue(
                packet.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet(
                    value
                ).accepted
            )

    def test_history_directory_builder_uses_repeatable_archives(self):
        with tempfile.TemporaryDirectory() as root:
            first = self.write_history(root, self.history_value("promote", "packet-a"), "history-a")
            second = self.write_history(
                root, self.history_value("promote", "packet-b"), "history-b"
            )
            value = packet.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_from_history_directories(
                (first, second), packet_id="packet:histories"
            )
            self.assertEqual(value.packet_id, "packet:histories")
            self.assertEqual(len(value.observatory.observations), 2)
            self.assertEqual(value.runtime.policy_evaluation.check_count, 8)


class PacketCliTests(PacketFixture):
    base = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-packet"

    def cli_json(self, arguments):
        output = StringIO()
        with redirect_stdout(output):
            status = main(arguments)
        return status, json.loads(output.getvalue())

    def test_cli_schema_capability_and_verification_commands(self):
        commands = (
            f"{self.base}-schema",
            f"{self.base}-capabilities",
            f"{self.base}-query-schema",
            f"{self.base}-query-capabilities",
            f"{self.base}-verification-schema",
            f"{self.base}-verification-capabilities",
        )
        for command in commands:
            status, output = self.cli_json([command])
            self.assertEqual(status, 0, command)
            self.assertTrue(output, command)

    def test_cli_build_query_and_verify_from_observatory_directory(self):
        with tempfile.TemporaryDirectory() as root:
            observatory_directory, runtime_directory = self.write_observatory_and_runtime(root)
            destination = Path(root) / "packet"
            status, summary = self.cli_json(
                [
                    self.base,
                    "--observatory-directory",
                    str(observatory_directory),
                    "--runtime-directory",
                    str(runtime_directory),
                    "--destination",
                    str(destination),
                    "--format",
                    "summary",
                ]
            )
            self.assertEqual(status, 0)
            self.assertEqual(summary["artifact_count"], 4)
            self.assertTrue(destination.is_dir())
            status, query = self.cli_json(
                [
                    f"{self.base}-query",
                    "--input",
                    str(destination),
                    "--resource",
                    "policy-checks",
                    "--passed",
                ]
            )
            self.assertEqual(status, 0)
            self.assertEqual(query["total"], 8)
            status, verification = self.cli_json(
                [f"{self.base}-verify", "--input", str(destination)]
            )
            self.assertEqual(status, 0)
            self.assertTrue(verification["accepted"])

    def test_cli_builds_from_repeatable_history_directories(self):
        with tempfile.TemporaryDirectory() as root:
            first = self.write_history(root, self.history_value("promote", "cli-a"), "history-a")
            second = self.write_history(root, self.history_value("promote", "cli-b"), "history-b")
            status, summary = self.cli_json(
                [
                    self.base,
                    "--history-directory",
                    str(first),
                    "--history-directory",
                    str(second),
                    "--packet-id",
                    "packet:cli",
                    "--format",
                    "summary",
                ]
            )
            self.assertEqual(status, 0)
            self.assertEqual(summary["packet_id"], "packet:cli")
            self.assertEqual(summary["state"], "ready")

    def test_cli_markdown_and_csv_exports_are_nonempty(self):
        with tempfile.TemporaryDirectory() as root:
            observatory_directory, runtime_directory = self.write_observatory_and_runtime(root)
            for output_format, marker in (
                ("csv", "file_name"),
                ("markdown", "# Packet"),
                ("json", '"packet_id"'),
            ):
                arguments = [
                    self.base,
                    "--observatory-directory",
                    str(observatory_directory),
                    "--runtime-directory",
                    str(runtime_directory),
                    "--format",
                    output_format,
                ]
                output = StringIO()
                with redirect_stdout(output):
                    status = main(arguments)
                self.assertEqual(status, 0)
                self.assertIn(marker, output.getvalue())


class PacketApiTests(PacketFixture):
    base = "/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/observatory"

    def test_api_packet_schema_and_capabilities(self):
        server = create_server(
            "127.0.0.1", 0, Path(tempfile.gettempdir()) / "glio-noncode-api-packet"
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            for suffix in (
                "/packet/schema",
                "/packet/capabilities",
                "/packet/query/schema",
                "/packet/query/capabilities",
                "/packet/verification/schema",
                "/packet/verification/capabilities",
            ):
                status, content_type, payload = self.http_json(server, self.base + suffix)
                self.assertEqual(status, 200, suffix)
                self.assertIn("application/json", content_type)
                self.assertTrue(payload, suffix)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_api_build_query_and_verify_packet(self):
        with tempfile.TemporaryDirectory() as root:
            first = self.write_history(root, self.history_value("promote", "api-a"), "history-a")
            second = self.write_history(root, self.history_value("promote", "api-b"), "history-b")
            packet_directory = Path(root) / "packet"
            value = packet.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_from_history_directories(
                (first, second), packet_id="packet:api"
            )
            packet.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet(
                value, packet_directory
            )
            server = create_server("127.0.0.1", 0, Path(root) / "api-data")
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                status, _, summary = self.http_json(
                    server,
                    self.base + "/packet",
                    {"history_directory": (str(first), str(second))},
                )
                self.assertEqual(status, 200)
                self.assertEqual(summary["artifact_count"], 4)
                status, _, query = self.http_json(
                    server,
                    self.base + "/packet/query",
                    {"input": str(packet_directory), "resource": "observations", "limit": "1"},
                )
                self.assertEqual(status, 200)
                self.assertEqual(query["total"], 2)
                self.assertEqual(len(query["items"]), 1)
                status, _, verification = self.http_json(
                    server,
                    self.base + "/packet/verify",
                    {"input": str(packet_directory)},
                )
                self.assertEqual(status, 200)
                self.assertTrue(verification["accepted"])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_api_format_negotiation_is_deterministic(self):
        with tempfile.TemporaryDirectory() as root:
            first = self.write_history(root, self.history_value("promote", "format-a"), "history-a")
            second = self.write_history(
                root, self.history_value("promote", "format-b"), "history-b"
            )
            server = create_server("127.0.0.1", 0, Path(root) / "api-data")
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                for output_format, marker in (("csv", "file_name"), ("markdown", "# Packet")):
                    status, content_type, payload = self.http_text(
                        server,
                        self.base + "/packet/query",
                        {
                            "history_directory": (str(first), str(second)),
                            "resource": "artifacts",
                            "format": output_format,
                        },
                    )
                    self.assertEqual(status, 200)
                    self.assertTrue(content_type)
                    self.assertIn(marker, payload)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


class PacketRealDataTests(PacketFixture):
    def test_real_downloaded_packet_closes_into_exact_handoff(self):
        packet_directory = self.real_packet()
        if not packet_directory.is_dir():
            self.skipTest("retained downloaded packet fixture is not installed")
        with tempfile.TemporaryDirectory() as root:
            history_value = history.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_from_directories(
                packet_directory,
                packet_directory,
                history_id="history:downloaded-packet",
            )
            history_directory = self.write_history(root, history_value, "downloaded-history")
            value = packet.build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_from_history_directories(
                (history_directory, history_directory),
                observation_ids=("downloaded-baseline", "downloaded-rerun"),
                packet_id="packet:downloaded",
            )
            destination = Path(root) / "downloaded-packet"
            packet.write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet(
                value, destination
            )
            loaded = packet.load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet(
                destination
            )
            self.assertTrue(loaded.accepted)
            self.assertTrue(loaded.release_ready)
            self.assertEqual(
                loaded.observatory.observations[0].observation_id, "downloaded-baseline"
            )
            self.assertEqual(loaded.observatory.observations[1].observation_id, "downloaded-rerun")
            self.assertEqual(loaded.runtime.policy_evaluation.check_count, 8)
            self.assertEqual(
                packet.verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet(
                    loaded
                ).failed_count,
                0,
            )


if __name__ == "__main__":
    unittest.main()
