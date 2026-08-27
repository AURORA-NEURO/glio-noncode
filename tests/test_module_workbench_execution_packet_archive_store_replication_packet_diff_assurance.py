"""Deep tests for independent packet-diff assurance and release readiness."""

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
)
from glio_noncode.module_workbench_execution_packet_archive_store_replication import (
    build_module_workbench_execution_packet_archive_store_replication,
)
from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet import (
    build_module_workbench_execution_packet_archive_store_replication_packet,
    write_module_workbench_execution_packet_archive_store_replication_packet,
)
from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff import (
    build_module_workbench_execution_packet_archive_store_replication_packet_diff,
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_release,
)
from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_assurance import (  # noqa: E501
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAssuranceState,
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_assurance,
    module_workbench_execution_packet_archive_store_replication_packet_diff_assurance_capabilities,
    module_workbench_execution_packet_archive_store_replication_packet_diff_assurance_csv,
    module_workbench_execution_packet_archive_store_replication_packet_diff_assurance_json,
    module_workbench_execution_packet_archive_store_replication_packet_diff_assurance_query_csv,
    module_workbench_execution_packet_archive_store_replication_packet_diff_assurance_query_json,
    module_workbench_execution_packet_archive_store_replication_packet_diff_assurance_schema,
    query_module_workbench_execution_packet_archive_store_replication_packet_diff_assurance,
    render_module_workbench_execution_packet_archive_store_replication_packet_diff_assurance_markdown,
    render_module_workbench_execution_packet_archive_store_replication_packet_diff_assurance_query_markdown,
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_assurance,
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_assurance_query,
)
from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_runtime import (  # noqa: E501
    run_module_workbench_execution_packet_archive_store_replication_packet_diff_runtime,
)
from glio_noncode.module_workbench_execution_packet_archive_store_replication_runtime import (
    run_module_workbench_execution_packet_archive_store_replication_runtime,
)
from glio_noncode.serialization import canonical_json
from tests.test_module_workbench_execution import ModuleWorkbenchExecutionFixture


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAssuranceTests(
    unittest.TestCase
):
    """Exercise independent assurance states and public projections."""

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

    def base_values(self):
        source, target = self.stores()
        plan = build_module_workbench_execution_packet_archive_store_replication(source, target)
        packet, _ = build_module_workbench_execution_packet_archive_store_replication_packet(
            plan, packet_id="assurance-packet"
        )
        diff = build_module_workbench_execution_packet_archive_store_replication_packet_diff(
            packet, packet
        )
        release = (
            build_module_workbench_execution_packet_archive_store_replication_packet_diff_release(
                diff
            )
        )
        return packet, diff, release, source, target

    def test_matched_packet_has_accepted_release_ready_assurance(self) -> None:
        packet, diff, release, _, _ = self.base_values()
        report = (
            build_module_workbench_execution_packet_archive_store_replication_packet_diff_assurance(
                diff, release
            )
        )
        self.assertEqual(
            report.state,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAssuranceState.ACCEPTED,
        )
        self.assertTrue(report.accepted)
        self.assertTrue(report.release_ready)
        self.assertEqual(report.blocker_count, 0)
        self.assertEqual(report.warning_count, 0)
        self.assertEqual(report.passed_count, report.finding_count)
        self.assertEqual(report.diff_address, diff.content_address)
        self.assertEqual(report.release_address, release.content_address)
        self.assertEqual(packet.plan_address, diff.left_plan_address)

    def test_extension_with_runtime_remains_release_ready(self) -> None:
        packet, diff, _, source, target = self.base_values()
        replication_runtime = (
            run_module_workbench_execution_packet_archive_store_replication_runtime(source, target)
        )
        plan = build_module_workbench_execution_packet_archive_store_replication(source, target)
        candidate, _ = build_module_workbench_execution_packet_archive_store_replication_packet(
            plan, runtime=replication_runtime, packet_id="assurance-packet"
        )
        extension = build_module_workbench_execution_packet_archive_store_replication_packet_diff(
            packet, candidate
        )
        release = (
            build_module_workbench_execution_packet_archive_store_replication_packet_diff_release(
                extension
            )
        )
        report = (
            build_module_workbench_execution_packet_archive_store_replication_packet_diff_assurance(
                extension, release
            )
        )
        self.assertEqual(extension.state.value, "extended")
        self.assertTrue(release.accepted)
        self.assertTrue(report.accepted)
        self.assertTrue(report.release_ready)
        self.assertEqual(report.warning_count, 0)
        self.assertIsNotNone(diff.content_address)

    def test_changed_content_is_accepted_for_review_but_not_release_ready(self) -> None:
        packet, _, _, source, target = self.base_values()
        changed_plan = build_module_workbench_execution_packet_archive_store_replication(
            source, target, replication_id="changed-plan"
        )
        candidate, _ = build_module_workbench_execution_packet_archive_store_replication_packet(
            changed_plan, packet_id="assurance-packet"
        )
        diff = build_module_workbench_execution_packet_archive_store_replication_packet_diff(
            packet, candidate
        )
        release = (
            build_module_workbench_execution_packet_archive_store_replication_packet_diff_release(
                diff
            )
        )
        report = (
            build_module_workbench_execution_packet_archive_store_replication_packet_diff_assurance(
                diff, release
            )
        )
        self.assertEqual(
            report.state,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAssuranceState.HOLD,
        )
        self.assertTrue(report.accepted)
        self.assertFalse(report.release_ready)
        self.assertGreater(report.warning_count, 0)
        self.assertEqual(report.blocker_count, 0)

    def test_runtime_is_retained_as_optional_assurance_evidence(self) -> None:
        packet, diff, release, _, _ = self.base_values()
        runtime = (
            run_module_workbench_execution_packet_archive_store_replication_packet_diff_runtime(
                packet, packet
            )
        )
        report = (
            build_module_workbench_execution_packet_archive_store_replication_packet_diff_assurance(
                diff, release, runtime
            )
        )
        self.assertTrue(report.accepted)
        self.assertTrue(report.release_ready)
        self.assertEqual(report.runtime_address, runtime.content_address)
        self.assertEqual(report.finding_count, 8)

    def test_finding_addresses_and_report_address_verify(self) -> None:
        _, diff, release, _, _ = self.base_values()
        report = (
            build_module_workbench_execution_packet_archive_store_replication_packet_diff_assurance(
                diff, release
            )
        )
        self.assertIs(
            verify_module_workbench_execution_packet_archive_store_replication_packet_diff_assurance(
                report
            ),
            report,
        )
        for finding in report.findings:
            self.assertIn("assurance-finding:", finding.content_address)
        self.assertIn("assurance:", report.content_address)

    def test_exports_are_canonical_and_reviewable(self) -> None:
        _, diff, release, _, _ = self.base_values()
        report = (
            build_module_workbench_execution_packet_archive_store_replication_packet_diff_assurance(
                diff, release
            )
        )
        self.assertEqual(
            json.loads(
                module_workbench_execution_packet_archive_store_replication_packet_diff_assurance_json(
                    report
                )
            ),
            json.loads(canonical_json(report.to_dict())),
        )
        csv_text = (
            module_workbench_execution_packet_archive_store_replication_packet_diff_assurance_csv(
                report
            )
        )
        markdown = render_module_workbench_execution_packet_archive_store_replication_packet_diff_assurance_markdown(  # noqa: E501
            report
        )
        self.assertIn("finding_id", csv_text)
        self.assertIn("# Archive Store Replication Packet Diff Assurance", markdown)
        self.assertIn(report.content_address, markdown)

    def test_query_filters_findings_and_verifies_address(self) -> None:
        _, diff, release, _, _ = self.base_values()
        report = (
            build_module_workbench_execution_packet_archive_store_replication_packet_diff_assurance(
                diff, release
            )
        )
        result = (
            query_module_workbench_execution_packet_archive_store_replication_packet_diff_assurance(
                report, resource="findings", severity="blocker", passed=True, limit=3
            )
        )
        self.assertEqual(result["total"], 4)
        self.assertEqual(len(result["items"]), 3)
        self.assertTrue(all(item["severity"] == "blocker" for item in result["items"]))
        self.assertTrue(all(item["passed"] for item in result["items"]))
        verified = verify_module_workbench_execution_packet_archive_store_replication_packet_diff_assurance_query(  # noqa: E501
            result
        )
        self.assertEqual(verified["content_address"], result["content_address"])
        self.assertEqual(
            json.loads(
                module_workbench_execution_packet_archive_store_replication_packet_diff_assurance_query_json(
                    result
                )
            ),
            json.loads(canonical_json(result)),
        )

    def test_query_exports_and_text_search_are_bounded(self) -> None:
        _, diff, release, _, _ = self.base_values()
        report = (
            build_module_workbench_execution_packet_archive_store_replication_packet_diff_assurance(
                diff, release
            )
        )
        result = (
            query_module_workbench_execution_packet_archive_store_replication_packet_diff_assurance(
                report, resource="findings", text="release", offset=0, limit=20
            )
        )
        self.assertGreater(result["total"], 0)
        csv_text = module_workbench_execution_packet_archive_store_replication_packet_diff_assurance_query_csv(  # noqa: E501
            result
        )
        markdown = render_module_workbench_execution_packet_archive_store_replication_packet_diff_assurance_query_markdown(  # noqa: E501
            result
        )
        self.assertIn("severity", csv_text)
        self.assertIn("# Archive Store Replication Packet Diff Assurance Query", markdown)
        with self.assertRaises(ValidationError):
            query_module_workbench_execution_packet_archive_store_replication_packet_diff_assurance(
                report, limit=513
            )

    def test_schema_and_capabilities_publish_the_gate_contract(self) -> None:
        schema = (
            module_workbench_execution_packet_archive_store_replication_packet_diff_assurance_schema()
        )
        capabilities = (
            module_workbench_execution_packet_archive_store_replication_packet_diff_assurance_capabilities()
        )
        self.assertIn("release_gate", schema)
        self.assertIn("blocker", schema["severities"])
        self.assertIn("audit_packet_diff", capabilities["operations"])
        self.assertIn("blockers_fail_closed", capabilities["guarantees"])

    def test_http_api_exposes_diff_and_assurance_from_persisted_packets(self) -> None:
        packet, _, _, source, target = self.base_values()
        plan = build_module_workbench_execution_packet_archive_store_replication(source, target)
        persisted_packet, payloads = (
            build_module_workbench_execution_packet_archive_store_replication_packet(
                plan, packet_id=packet.packet_id
            )
        )
        with tempfile.TemporaryDirectory() as directory:
            left = Path(directory) / "left"
            right = Path(directory) / "right"
            write_module_workbench_execution_packet_archive_store_replication_packet(
                persisted_packet, payloads, left
            )
            write_module_workbench_execution_packet_archive_store_replication_packet(
                persisted_packet, payloads, right
            )
            server = create_server("127.0.0.1", 0, directory)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            connection = None
            try:
                host, port = server.server_address
                connection = HTTPConnection(host, port, timeout=30)
                query = urlencode(
                    {
                        "left_directory": str(left),
                        "right_directory": str(right),
                        "format": "summary",
                    }
                )
                connection.request(
                    "GET",
                    "/v1/module-workbench/execution/packet/archive/store/replication/packet/diff?"
                    + query,
                )
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                diff_payload = json.loads(response.read())
                self.assertEqual(diff_payload["state"], "matched")
                connection.request(
                    "GET",
                    "/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/assurance?"
                    + query,
                )
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                assurance_payload = json.loads(response.read())
                self.assertEqual(assurance_payload["state"], "accepted")
                connection.request(
                    "GET",
                    "/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/schema",
                )
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertTrue(json.loads(response.read())["fail_closed"])
                batch_query = urlencode(
                    [
                        ("pair", f"same={left}={right}"),
                        ("format", "summary"),
                    ]
                )
                connection.request(
                    "GET",
                    "/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/batch?"
                    + batch_query,
                )
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                batch_payload = json.loads(response.read())
                self.assertEqual(batch_payload["item_count"], 1)
                self.assertTrue(batch_payload["release_ready"])
            finally:
                if connection is not None:
                    connection.close()
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_public_assurance_documents_are_path_free(self) -> None:
        _, diff, release, _, _ = self.base_values()
        report = (
            build_module_workbench_execution_packet_archive_store_replication_packet_diff_assurance(
                diff, release
            )
        )
        documents = (
            module_workbench_execution_packet_archive_store_replication_packet_diff_assurance_json(
                report
            ),
            module_workbench_execution_packet_archive_store_replication_packet_diff_assurance_csv(
                report
            ),
        )
        for document in documents:
            lowered = document.casefold()
            self.assertNotIn("agent", lowered)
            self.assertNotIn("assistant", lowered)
            self.assertNotIn("username", lowered)
            self.assertNotIn("c:\\", lowered)

    def test_tampered_report_and_query_fail_closed(self) -> None:
        _, diff, release, _, _ = self.base_values()
        report = (
            build_module_workbench_execution_packet_archive_store_replication_packet_diff_assurance(
                diff, release
            )
        )
        report.detail = "tampered"
        with self.assertRaises(ValidationError):
            verify_module_workbench_execution_packet_archive_store_replication_packet_diff_assurance(
                report
            )
        with self.assertRaises(ValidationError):
            query_module_workbench_execution_packet_archive_store_replication_packet_diff_assurance(
                report
            )
        clean_report = (
            build_module_workbench_execution_packet_archive_store_replication_packet_diff_assurance(
                diff, release
            )
        )
        result = (
            query_module_workbench_execution_packet_archive_store_replication_packet_diff_assurance(
                clean_report
            )
        )
        with self.assertRaises(ValidationError):
            verify_module_workbench_execution_packet_archive_store_replication_packet_diff_assurance_query(
                result | {"accepted": False}
            )


if __name__ == "__main__":
    unittest.main()
