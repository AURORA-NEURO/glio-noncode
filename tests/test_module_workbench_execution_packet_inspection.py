"""Deep regression coverage for packet inspection and review findings."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main
from glio_noncode.module_workbench_execution_packet import (
    build_module_workbench_execution_packet,
    write_module_workbench_execution_packet,
)
from glio_noncode.module_workbench_execution_packet_inspection import (
    build_module_workbench_execution_packet_inspection,
    module_workbench_execution_packet_inspection_capabilities,
    module_workbench_execution_packet_inspection_csv,
    module_workbench_execution_packet_inspection_json,
    module_workbench_execution_packet_inspection_schema,
    query_module_workbench_execution_packet_inspection,
    render_module_workbench_execution_packet_inspection_markdown,
    verify_module_workbench_execution_packet_inspection,
)
from glio_noncode.module_workbench_execution_packet_inspection_contracts import (
    MODULE_WORKBENCH_EXECUTION_PACKET_INSPECTION_BOUNDARY,
    ModuleWorkbenchExecutionPacketInspectionPlane,
    ModuleWorkbenchExecutionPacketInspectionSeverity,
    ModuleWorkbenchExecutionPacketInspectionState,
)
from tests.test_module_workbench_execution import ModuleWorkbenchExecutionFixture


class ModuleWorkbenchExecutionPacketInspectionTests(unittest.TestCase):
    """Exercise review normalization from typed and persisted packet inputs."""

    def setUp(self) -> None:
        self.fixture = ModuleWorkbenchExecutionFixture()
        self.fixture.setUp()

    def tearDown(self) -> None:
        self.fixture.tearDown()

    def packet(self):
        return build_module_workbench_execution_packet(self.fixture.report())

    def write_packet(self, packet):
        directory = tempfile.TemporaryDirectory()
        path = Path(directory.name) / "execution-packet"
        write_module_workbench_execution_packet(packet, path)
        self.addCleanup(directory.cleanup)
        return path

    def test_typed_inspection_accepts_and_conserves_findings(self) -> None:
        packet = self.packet()
        inspection = build_module_workbench_execution_packet_inspection(packet)
        self.assertTrue(inspection.accepted)
        self.assertEqual(inspection.state, ModuleWorkbenchExecutionPacketInspectionState.ACCEPTED)
        self.assertEqual(inspection.check_count, inspection.finding_count)
        self.assertEqual(
            inspection.passed_check_count + inspection.failed_check_count,
            inspection.check_count,
        )
        self.assertEqual(inspection.failed_finding_count, 0)
        self.assertEqual(inspection.critical_count, 0)
        self.assertEqual(inspection.packet_address, packet.content_address)
        self.assertEqual(
            inspection.release_address.split(":", 1)[0],
            "module-workbench-execution-packet-release",
        )
        self.assertEqual(
            tuple(item.finding_id for item in inspection.findings),
            tuple(sorted(item.finding_id for item in inspection.findings)),
        )
        self.assertEqual(
            {item.plane for item in inspection.findings},
            {
                ModuleWorkbenchExecutionPacketInspectionPlane.BYTES,
                ModuleWorkbenchExecutionPacketInspectionPlane.SEMANTIC,
                ModuleWorkbenchExecutionPacketInspectionPlane.PUBLIC,
                ModuleWorkbenchExecutionPacketInspectionPlane.RELEASE,
            },
        )
        self.assertTrue(
            all(
                item.severity is ModuleWorkbenchExecutionPacketInspectionSeverity.INFO
                for item in inspection.findings
            )
        )
        verify_module_workbench_execution_packet_inspection(inspection)

    def test_persisted_inspection_uses_storage_verification(self) -> None:
        path = self.write_packet(self.packet())
        inspection = build_module_workbench_execution_packet_inspection(path)
        self.assertTrue(inspection.accepted)
        self.assertEqual(inspection.artifact_count, 13)
        self.assertEqual(
            inspection.packet_address.split(":", 1)[0],
            "module-workbench-execution-packet",
        )
        self.assertEqual(
            inspection.verification_address.split(":", 1)[0],
            "module-workbench-execution-packet-verification",
        )
        self.assertEqual(
            inspection.replay_address.split(":", 1)[0],
            "module-workbench-execution-packet-replay",
        )
        self.assertEqual(inspection.finding_count, 17)
        self.assertTrue(all(item.passed for item in inspection.findings))

    def test_summary_and_finding_queries_are_bounded(self) -> None:
        inspection = build_module_workbench_execution_packet_inspection(self.packet())
        summary = query_module_workbench_execution_packet_inspection(inspection, resource="summary")
        findings = query_module_workbench_execution_packet_inspection(
            inspection,
            resource="findings",
        )
        self.assertEqual(summary["total"], 1)
        self.assertEqual(
            summary["items"][0]["boundary"],
            MODULE_WORKBENCH_EXECUTION_PACKET_INSPECTION_BOUNDARY,
        )
        self.assertEqual(findings["total"], inspection.finding_count)
        self.assertEqual(len(findings["items"]), inspection.finding_count)
        self.assertEqual(findings["index_used"], "finding_id")
        self.assertEqual(findings["offset"], 0)

    def test_finding_filters_cover_severity_plane_code_result_and_text(self) -> None:
        inspection = build_module_workbench_execution_packet_inspection(self.packet())
        for kwargs, expected in (
            ({"plane": "release"}, 6),
            ({"severity": "info"}, inspection.finding_count),
            ({"passed": True}, inspection.finding_count),
            ({"code": "release:packet-accepted"}, 1),
            ({"text": "public"}, 2),
        ):
            result = query_module_workbench_execution_packet_inspection(
                inspection,
                resource="findings",
                **kwargs,
            )
            self.assertEqual(result["total"], expected, kwargs)
        paged = query_module_workbench_execution_packet_inspection(
            inspection,
            resource="findings",
            offset=2,
            limit=3,
        )
        self.assertEqual(paged["total"], inspection.finding_count)
        self.assertEqual(len(paged["items"]), 3)
        self.assertEqual(paged["items"][0]["finding_id"], inspection.findings[2].finding_id)

    def test_exports_are_deterministic_and_complete(self) -> None:
        inspection = build_module_workbench_execution_packet_inspection(self.packet())
        json_text = module_workbench_execution_packet_inspection_json(inspection)
        csv_text = module_workbench_execution_packet_inspection_csv(inspection)
        markdown = render_module_workbench_execution_packet_inspection_markdown(inspection)
        self.assertTrue(json_text.endswith("\n"))
        self.assertIn('"findings"', json_text)
        self.assertIn("finding_id,plane,severity,code,passed", csv_text)
        self.assertEqual(csv_text.count("\n"), inspection.finding_count + 1)
        self.assertIn("# Module Workbench Execution Packet Inspection", markdown)
        self.assertIn("Critical failures", markdown)
        self.assertEqual(json_text, module_workbench_execution_packet_inspection_json(inspection))

    def test_schema_and_capabilities_are_identity_free(self) -> None:
        schema = module_workbench_execution_packet_inspection_schema()
        capabilities = module_workbench_execution_packet_inspection_capabilities()
        self.assertEqual(schema["boundary"], MODULE_WORKBENCH_EXECUTION_PACKET_INSPECTION_BOUNDARY)
        self.assertEqual(schema["resources"], ["findings", "summary"])
        self.assertTrue(schema["path_free"])
        self.assertTrue(schema["timestamp_free"])
        self.assertTrue(schema["identity_free"])
        self.assertEqual(capabilities["operation_count"], len(capabilities["operations"]))
        self.assertTrue(capabilities["deterministic"])
        self.assertTrue(capabilities["offline"])
        self.assertTrue(capabilities["bounded"])
        self.assertTrue(capabilities["identity_free"])

    def test_typed_payload_tamper_becomes_critical_review(self) -> None:
        packet = self.packet()
        object.__setattr__(packet.artifacts[0], "payload", "tampered")
        inspection = build_module_workbench_execution_packet_inspection(packet)
        self.assertFalse(inspection.accepted)
        self.assertEqual(inspection.state, ModuleWorkbenchExecutionPacketInspectionState.BLOCKED)
        self.assertGreaterEqual(inspection.critical_count, 1)
        self.assertTrue(any(not item.passed for item in inspection.findings))
        self.assertTrue(
            any(
                item.severity is ModuleWorkbenchExecutionPacketInspectionSeverity.CRITICAL
                and not item.passed
                for item in inspection.findings
            )
        )

    def test_persisted_byte_tamper_survives_as_blocked_review(self) -> None:
        path = self.write_packet(self.packet())
        artifact = path / "audit.json"
        artifact.write_text(artifact.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        inspection = build_module_workbench_execution_packet_inspection(path)
        self.assertFalse(inspection.accepted)
        self.assertEqual(inspection.packet_address, "unavailable")
        self.assertGreaterEqual(inspection.failed_finding_count, 1)
        failed = query_module_workbench_execution_packet_inspection(
            inspection,
            resource="findings",
            passed=False,
        )
        self.assertEqual(failed["total"], inspection.failed_finding_count)
        self.assertTrue(any(item["plane"] == "bytes" for item in failed["items"]))

    def test_cli_inspection_schema_capabilities_and_exports(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "result.json"
            for command in (
                "module-workbench-execution-packet-inspection-schema",
                "module-workbench-execution-packet-inspection-capabilities",
            ):
                self.assertEqual(main([command, "--output", str(output)]), 0)
                self.assertTrue(output.read_text(encoding="utf-8").strip())
            packet_dir = Path(directory) / "packet"
            packet = self.packet()
            write_module_workbench_execution_packet(packet, packet_dir)
            self.assertEqual(
                main(
                    [
                        "module-workbench-execution-packet-inspection",
                        str(packet_dir),
                        "--format",
                        "markdown",
                        "--output",
                        str(output),
                    ]
                ),
                0,
            )
            self.assertIn("Inspection", output.read_text(encoding="utf-8"))
            self.assertEqual(
                main(
                    [
                        "module-workbench-execution-packet-inspection-query",
                        str(packet_dir),
                        "--plane",
                        "release",
                        "--output",
                        str(output),
                    ]
                ),
                0,
            )
            self.assertIn('"total": 6', output.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
