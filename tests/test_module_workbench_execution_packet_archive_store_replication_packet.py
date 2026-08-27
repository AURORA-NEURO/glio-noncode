"""Deep tests for deterministic replication packet construction and transport."""

from __future__ import annotations

import json
import tempfile
import unittest
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread
from urllib.parse import urlencode

from glio_noncode.api import create_server
from glio_noncode.errors import ValidationError
from glio_noncode.module_workbench_execution_packet import (
    build_module_workbench_execution_packet,
)
from glio_noncode.module_workbench_execution_packet_archive import (
    build_module_workbench_execution_packet_archive,
)
from glio_noncode.module_workbench_execution_packet_archive_store import (
    append_module_workbench_execution_packet_archive_store,
    build_module_workbench_execution_packet_archive_store,
    write_module_workbench_execution_packet_archive_store,
)
from glio_noncode.module_workbench_execution_packet_archive_store_replication import (
    build_module_workbench_execution_packet_archive_store_promotion,
    build_module_workbench_execution_packet_archive_store_replication,
)
from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet import (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_ARTIFACT_DIRECTORY,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketArtifactRole,
    build_module_workbench_execution_packet_archive_store_replication_packet,
    load_module_workbench_execution_packet_archive_store_replication_packet,
    module_workbench_execution_packet_archive_store_replication_packet_capabilities,
    module_workbench_execution_packet_archive_store_replication_packet_csv,
    module_workbench_execution_packet_archive_store_replication_packet_json,
    module_workbench_execution_packet_archive_store_replication_packet_query_csv,
    module_workbench_execution_packet_archive_store_replication_packet_query_json,
    module_workbench_execution_packet_archive_store_replication_packet_schema,
    query_module_workbench_execution_packet_archive_store_replication_packet,
    render_module_workbench_execution_packet_archive_store_replication_packet_markdown,
    render_module_workbench_execution_packet_archive_store_replication_packet_query_markdown,
    replay_module_workbench_execution_packet_archive_store_replication_packet,
    verify_module_workbench_execution_packet_archive_store_replication_packet,
    verify_module_workbench_execution_packet_archive_store_replication_packet_query,
    write_module_workbench_execution_packet_archive_store_replication_packet,
)
from glio_noncode.module_workbench_execution_packet_archive_store_replication_runtime import (
    run_module_workbench_execution_packet_archive_store_replication_runtime,
)
from glio_noncode.serialization import canonical_json
from tests.test_module_workbench_execution import ModuleWorkbenchExecutionFixture


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketTests(unittest.TestCase):
    """Exercise packet identity, content, persistence, and query boundaries."""

    def setUp(self) -> None:
        self.fixture = ModuleWorkbenchExecutionFixture()
        self.fixture.setUp()

    def tearDown(self) -> None:
        self.fixture.tearDown()

    def archive(self, packet_id: str, archive_id: str):
        packet = build_module_workbench_execution_packet(self.fixture.report(), packet_id=packet_id)
        return build_module_workbench_execution_packet_archive(packet, archive_id=archive_id)

    def stores(self):
        base = self.archive("base", "base")
        next_archive = self.archive("next", "next")
        target = build_module_workbench_execution_packet_archive_store((base,), store_id="target")
        source = append_module_workbench_execution_packet_archive_store(
            target, next_archive, operation_id="next-operation"
        )
        return source, target

    def typed_packet(self, *, with_runtime: bool = True):
        source, target = self.stores()
        plan = build_module_workbench_execution_packet_archive_store_replication(source, target)
        runtime = None
        receipt = None
        promotion = None
        if with_runtime:
            with tempfile.TemporaryDirectory() as temporary:
                runtime = run_module_workbench_execution_packet_archive_store_replication_runtime(
                    source,
                    target,
                    apply=True,
                    destination=Path(temporary) / "applied",
                )
        promotion = build_module_workbench_execution_packet_archive_store_promotion(plan)
        packet, payloads = build_module_workbench_execution_packet_archive_store_replication_packet(
            plan, promotion=promotion, runtime=runtime, receipt=receipt
        )
        return packet, payloads, plan

    def test_packet_has_fixed_roles_and_deterministic_manifest(self) -> None:
        packet_a, payloads_a, plan_a = self.typed_packet(with_runtime=False)
        packet_b, payloads_b, plan_b = self.typed_packet(with_runtime=False)
        self.assertEqual(packet_a.content_address, packet_b.content_address)
        self.assertEqual(payloads_a, payloads_b)
        self.assertEqual(packet_a.plan_address, plan_a.content_address)
        self.assertEqual(packet_a.artifact_count, 5)
        self.assertEqual(packet_a.check_count, 5)
        self.assertEqual(packet_a.passed_count, 5)
        self.assertEqual(packet_a.total_byte_count, sum(map(len, payloads_a.values())))
        self.assertEqual(
            {item.role for item in packet_a.artifacts},
            {
                ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketArtifactRole.PLAN,
                ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketArtifactRole.QUERY,
                ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketArtifactRole.PROMOTION,
            },
        )

    def test_runtime_packet_contains_runtime_and_receipt_artifacts(self) -> None:
        source, target = self.stores()
        plan = build_module_workbench_execution_packet_archive_store_replication(source, target)
        with tempfile.TemporaryDirectory() as temporary:
            runtime = run_module_workbench_execution_packet_archive_store_replication_runtime(
                source, target, apply=True, destination=Path(temporary) / "applied"
            )
            self.assertTrue(runtime.accepted)
            packet, payloads = (
                build_module_workbench_execution_packet_archive_store_replication_packet(
                    plan, runtime=runtime, receipt=None
                )
            )
        self.assertTrue(packet.accepted)
        self.assertEqual(packet.artifact_count, 7)
        self.assertIsNotNone(packet.runtime_address)
        self.assertIn("artifacts/runtime.json", payloads)
        self.assertIn("artifacts/runtime.csv", payloads)

    def test_manifest_json_csv_and_markdown_are_stable(self) -> None:
        packet, _, _ = self.typed_packet(with_runtime=False)
        json_text = module_workbench_execution_packet_archive_store_replication_packet_json(packet)
        self.assertEqual(json.loads(json_text), json.loads(canonical_json(packet.to_dict())))
        csv_text = module_workbench_execution_packet_archive_store_replication_packet_csv(packet)
        self.assertIn("artifact_id", csv_text)
        self.assertEqual(csv_text.count("\n"), packet.artifact_count + 1)
        markdown = (
            render_module_workbench_execution_packet_archive_store_replication_packet_markdown(
                packet
            )
        )
        self.assertIn("# Archive Store Replication Packet", markdown)
        self.assertIn(packet.content_address, markdown)
        self.assertNotIn("C:\\", markdown)

    def test_verification_accepts_manifest_and_payloads(self) -> None:
        packet, payloads, _ = self.typed_packet(with_runtime=False)
        verification = verify_module_workbench_execution_packet_archive_store_replication_packet(
            packet, payloads
        )
        self.assertTrue(verification.accepted)
        self.assertEqual(verification.artifact_count, packet.artifact_count)
        self.assertEqual(verification.passed_count, verification.check_count)
        self.assertGreaterEqual(verification.check_count, 8)

    def test_missing_payload_is_rejected(self) -> None:
        packet, payloads, _ = self.typed_packet(with_runtime=False)
        missing = dict(payloads)
        missing.pop("artifacts/plan.csv")
        verification = verify_module_workbench_execution_packet_archive_store_replication_packet(
            packet, missing
        )
        self.assertFalse(verification.accepted)
        self.assertTrue(any(not item.passed for item in verification.checks))
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(ValidationError):
                write_module_workbench_execution_packet_archive_store_replication_packet(
                    packet, missing, Path(temporary) / "packet"
                )

    def test_tampered_payload_is_rejected_by_content_address(self) -> None:
        packet, payloads, _ = self.typed_packet(with_runtime=False)
        tampered = dict(payloads)
        tampered["artifacts/plan.json"] += b"tamper"
        verification = verify_module_workbench_execution_packet_archive_store_replication_packet(
            packet, tampered
        )
        self.assertFalse(verification.accepted)
        self.assertTrue(
            any(item.plane.value == "storage" and not item.passed for item in verification.checks)
        )

    def test_persisted_packet_round_trips_without_paths(self) -> None:
        packet, payloads, _ = self.typed_packet(with_runtime=False)
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "packet"
            written = write_module_workbench_execution_packet_archive_store_replication_packet(
                packet, payloads, destination
            )
            self.assertEqual(written, destination)
            loaded, loaded_payloads = (
                load_module_workbench_execution_packet_archive_store_replication_packet(destination)
            )
            self.assertEqual(loaded.content_address, packet.content_address)
            self.assertEqual(loaded_payloads, payloads)
            self.assertEqual(
                replay_module_workbench_execution_packet_archive_store_replication_packet(
                    destination
                ).accepted,
                True,
            )
            manifest = (destination / "packet.json").read_text(encoding="utf-8")
            self.assertNotIn(str(destination), manifest)
            self.assertTrue((destination / "artifacts" / "plan.json").is_file())

    def test_persisted_packet_rejects_extra_artifact(self) -> None:
        packet, payloads, _ = self.typed_packet(with_runtime=False)
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "packet"
            write_module_workbench_execution_packet_archive_store_replication_packet(
                packet, payloads, destination
            )
            (destination / "artifacts" / "unexpected.json").write_bytes(b"unexpected")
            with self.assertRaises(ValidationError):
                load_module_workbench_execution_packet_archive_store_replication_packet(destination)

    def test_persisted_packet_rejects_noncanonical_manifest(self) -> None:
        packet, payloads, _ = self.typed_packet(with_runtime=False)
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "packet"
            write_module_workbench_execution_packet_archive_store_replication_packet(
                packet, payloads, destination
            )
            manifest_path = destination / "packet.json"
            manifest_path.write_text(json.dumps(packet.to_dict(), indent=2), encoding="utf-8")
            with self.assertRaises(ValidationError):
                load_module_workbench_execution_packet_archive_store_replication_packet(destination)

    def test_atomic_writer_requires_explicit_existing_override(self) -> None:
        packet, payloads, _ = self.typed_packet(with_runtime=False)
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "packet"
            write_module_workbench_execution_packet_archive_store_replication_packet(
                packet, payloads, destination
            )
            with self.assertRaises(ValidationError):
                write_module_workbench_execution_packet_archive_store_replication_packet(
                    packet, payloads, destination
                )
            write_module_workbench_execution_packet_archive_store_replication_packet(
                packet, payloads, destination, allow_existing=True
            )
            self.assertTrue((destination / "packet.json").is_file())

    def test_query_artifacts_is_bounded_and_addressed(self) -> None:
        packet, _, _ = self.typed_packet(with_runtime=False)
        result = query_module_workbench_execution_packet_archive_store_replication_packet(
            packet,
            resource="artifacts",
            role="plan",
            limit=2,
        )
        self.assertEqual(result["resource"], "artifacts")
        self.assertEqual(result["total"], 3)
        self.assertEqual(len(result["items"]), 2)
        self.assertTrue(all(item["role"] == "plan" for item in result["items"]))
        verified = verify_module_workbench_execution_packet_archive_store_replication_packet_query(
            result
        )
        self.assertEqual(verified["content_address"], result["content_address"])

    def test_query_checks_filters_and_exports(self) -> None:
        packet, _, _ = self.typed_packet(with_runtime=False)
        result = query_module_workbench_execution_packet_archive_store_replication_packet(
            packet, resource="checks", accepted=True, text="packet"
        )
        json_text = module_workbench_execution_packet_archive_store_replication_packet_query_json(
            result
        )
        csv_text = module_workbench_execution_packet_archive_store_replication_packet_query_csv(
            result
        )
        render_query_markdown = (
            render_module_workbench_execution_packet_archive_store_replication_packet_query_markdown
        )
        markdown = render_query_markdown(result)
        self.assertEqual(json.loads(json_text), json.loads(canonical_json(result)))
        self.assertIn("passed", csv_text)
        self.assertIn("# Archive Store Replication Packet Query", markdown)

    def test_query_rejects_bad_resource_and_page(self) -> None:
        packet, _, _ = self.typed_packet(with_runtime=False)
        with self.assertRaises(ValidationError):
            query_module_workbench_execution_packet_archive_store_replication_packet(
                packet, resource="unknown"
            )
        with self.assertRaises(ValidationError):
            query_module_workbench_execution_packet_archive_store_replication_packet(
                packet, limit=513
            )
        with self.assertRaises(ValidationError):
            query_module_workbench_execution_packet_archive_store_replication_packet(
                packet, offset=-1
            )

    def test_schema_and_capabilities_publish_limits(self) -> None:
        schema = module_workbench_execution_packet_archive_store_replication_packet_schema()
        capabilities = (
            module_workbench_execution_packet_archive_store_replication_packet_capabilities()
        )
        self.assertTrue(schema["path_free_manifest"])
        self.assertTrue(schema["atomic_write"])
        self.assertIn("artifacts", schema["resources"])
        self.assertIn("write_packet_atomically", capabilities["operations"])
        self.assertIn("symlink_rejection", capabilities["guarantees"])

    def test_file_name_contract_is_explicit(self) -> None:
        packet, _, _ = self.typed_packet(with_runtime=False)
        self.assertTrue(
            all(
                item.file_name.startswith(
                    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_ARTIFACT_DIRECTORY
                    + "/"
                )
                for item in packet.artifacts
            )
        )
        self.assertEqual(
            {item.file_name.split("/", 1)[1] for item in packet.artifacts},
            {"plan.json", "plan.csv", "plan.md", "query-summary.json", "promotion.json"},
        )

    def test_plan_address_changes_packet_address(self) -> None:
        source, target = self.stores()
        plan = build_module_workbench_execution_packet_archive_store_replication(source, target)
        first, _ = build_module_workbench_execution_packet_archive_store_replication_packet(
            plan, packet_id="first"
        )
        second, _ = build_module_workbench_execution_packet_archive_store_replication_packet(
            plan, packet_id="second"
        )
        self.assertNotEqual(first.content_address, second.content_address)
        self.assertEqual(first.plan_address, second.plan_address)

    def test_blocked_promotion_can_still_be_reviewed_in_packet(self) -> None:
        source, target = self.stores()
        plan = build_module_workbench_execution_packet_archive_store_replication(source, target)
        promotion = build_module_workbench_execution_packet_archive_store_promotion(plan)
        self.assertFalse(promotion.accepted)
        packet, _ = build_module_workbench_execution_packet_archive_store_replication_packet(
            plan, promotion=promotion
        )
        self.assertTrue(packet.accepted)
        self.assertIn("artifacts/promotion.json", {item.file_name for item in packet.artifacts})

    def test_packet_content_is_path_free_and_identity_free(self) -> None:
        packet, payloads, _ = self.typed_packet(with_runtime=False)
        documents = [
            module_workbench_execution_packet_archive_store_replication_packet_json(packet)
        ]
        documents.extend(
            value.decode("utf-8") for value in payloads.values() if value.startswith(b"{")
        )
        forbidden = ("agent", "assistant", "model", "username", "C:\\")
        for document in documents:
            lowered = document.casefold()
            self.assertFalse(any(token in lowered for token in forbidden))

    def test_load_rejects_symlinked_artifact_when_supported(self) -> None:
        packet, payloads, _ = self.typed_packet(with_runtime=False)
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "packet"
            write_module_workbench_execution_packet_archive_store_replication_packet(
                packet, payloads, destination
            )
            original = destination / "artifacts" / "plan.json"
            backup = destination / "artifacts" / "plan-copy.json"
            original.replace(backup)
            try:
                original.symlink_to(backup)
            except (OSError, NotImplementedError):
                original.write_bytes(backup.read_bytes())
                self.skipTest("symbolic links are unavailable")
            with self.assertRaises(ValidationError):
                load_module_workbench_execution_packet_archive_store_replication_packet(destination)

    def test_api_exposes_packet_build_query_replay_and_contracts(self) -> None:
        source, target = self.stores()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_dir = root / "source"
            target_dir = root / "target"
            packet_dir = root / "packet"
            write_module_workbench_execution_packet_archive_store(source, source_dir)
            write_module_workbench_execution_packet_archive_store(target, target_dir)
            server = create_server(host="127.0.0.1", port=0)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                connection = HTTPConnection("127.0.0.1", server.server_port, timeout=30)

                def get(route: str) -> tuple[int, dict[str, object]]:
                    connection.request("GET", route)
                    response = connection.getresponse()
                    return response.status, json.loads(response.read().decode("utf-8"))

                for route, marker in (
                    (
                        "/v1/module-workbench/execution/packet/archive/store/replication/packet/schema",
                        "artifact_roles",
                    ),
                    (
                        "/v1/module-workbench/execution/packet/archive/store/replication/packet/capabilities",
                        "guarantees",
                    ),
                    (
                        "/v1/module-workbench/execution/packet/archive/store/replication/packet/query/schema",
                        "filters",
                    ),
                ):
                    status, payload = get(route)
                    self.assertEqual(status, 200)
                    self.assertIn(marker, payload)
                common = urlencode({"source_directory": source_dir, "target_directory": target_dir})
                status, payload = get(
                    "/v1/module-workbench/execution/packet/archive/store/replication/packet?"
                    + common
                    + "&destination="
                    + str(packet_dir)
                    + "&format=summary"
                )
                self.assertEqual(status, 200)
                self.assertTrue(payload["accepted"])
                self.assertEqual(payload["artifact_count"], 5)
                status, payload = get(
                    "/v1/module-workbench/execution/packet/archive/store/replication/packet/query?"
                    + common
                    + "&resource=artifacts&role=plan"
                )
                self.assertEqual(status, 200)
                self.assertEqual(payload["total"], 3)
                status, payload = get(
                    "/v1/module-workbench/execution/packet/archive/store/replication/packet/replay?"
                    + urlencode({"directory": packet_dir})
                )
                self.assertEqual(status, 200)
                self.assertTrue(payload["accepted"])
                self.assertNotIn("path", payload)
                self.assertNotIn("agent", payload)
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=10)


if __name__ == "__main__":
    unittest.main()
