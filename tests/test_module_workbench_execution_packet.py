"""Deep regression coverage for portable execution handoff packets."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.module_workbench_execution import execution_command
from glio_noncode.module_workbench_execution_packet import (
    build_module_workbench_execution_packet,
    load_module_workbench_execution_packet,
    module_workbench_execution_packet_capabilities,
    module_workbench_execution_packet_csv,
    module_workbench_execution_packet_json,
    module_workbench_execution_packet_schema,
    render_module_workbench_execution_packet_markdown,
    verify_module_workbench_execution_packet,
    verify_module_workbench_execution_packet_value,
    write_module_workbench_execution_packet,
)
from glio_noncode.module_workbench_execution_packet_contracts import (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARTIFACT_COUNT,
    MODULE_WORKBENCH_EXECUTION_PACKET_MANIFEST,
    ModuleWorkbenchExecutionPacketState,
)
from glio_noncode.module_workbench_execution_packet_query import (
    diff_module_workbench_execution_packets,
    module_workbench_execution_packet_query_capabilities,
    module_workbench_execution_packet_query_schema,
    query_module_workbench_execution_packet,
    replay_module_workbench_execution_packet,
)
from glio_noncode.module_workbench_execution_packet_release import (
    build_module_workbench_execution_packet_release,
    module_workbench_execution_packet_release_capabilities,
    module_workbench_execution_packet_release_csv,
    module_workbench_execution_packet_release_json,
    module_workbench_execution_packet_release_schema,
    query_module_workbench_execution_packet_release,
    render_module_workbench_execution_packet_release_markdown,
    verify_module_workbench_execution_packet_release,
)
from glio_noncode.module_workbench_execution_packet_release_contracts import (
    ModuleWorkbenchExecutionPacketReleaseState,
)
from glio_noncode.module_workbench_execution_packet_runtime import (
    module_workbench_execution_packet_runtime_capabilities,
    module_workbench_execution_packet_runtime_csv,
    module_workbench_execution_packet_runtime_json,
    module_workbench_execution_packet_runtime_schema,
    query_module_workbench_execution_packet_runtime,
    run_module_workbench_execution_packet_runtime,
    verify_module_workbench_execution_packet_runtime,
)
from glio_noncode.module_workbench_execution_packet_runtime_contracts import (
    ModuleWorkbenchExecutionPacketRuntimeStageKind,
)
from tests.test_module_workbench_execution import ModuleWorkbenchExecutionFixture


class ModuleWorkbenchExecutionPacketTests(unittest.TestCase):
    """Exercise the packet entirely through typed, filesystem, and export paths."""

    def setUp(self) -> None:
        self.fixture = ModuleWorkbenchExecutionFixture()
        self.fixture.setUp()

    def tearDown(self) -> None:
        self.fixture.tearDown()

    def packet(self, *commands):
        return build_module_workbench_execution_packet(self.fixture.report(), commands=commands)

    def write_packet(self, packet):
        directory = tempfile.TemporaryDirectory()
        path = Path(directory.name) / "execution-packet"
        write_module_workbench_execution_packet(packet, path)
        self.addCleanup(directory.cleanup)
        return path

    def test_build_has_fixed_artifact_set_and_address_chain(self) -> None:
        packet = self.packet()
        self.assertTrue(packet.accepted)
        self.assertEqual(packet.state, ModuleWorkbenchExecutionPacketState.ACCEPTED)
        self.assertEqual(packet.artifact_count, MODULE_WORKBENCH_EXECUTION_PACKET_ARTIFACT_COUNT)
        self.assertEqual(
            tuple(item.artifact_id for item in packet.artifacts),
            tuple(sorted(item.artifact_id for item in packet.artifacts)),
        )
        self.assertEqual(len(packet.checks), 14)
        self.assertEqual(packet.failed_check_count, 0)
        self.assertTrue(all(item.payload is not None for item in packet.artifacts))
        self.assertTrue(all("/" not in item.relative_path[:1] for item in packet.artifacts))
        self.assertIn("ledger", {item.artifact_id for item in packet.artifacts})
        self.assertIn("runtime", {item.artifact_id for item in packet.artifacts})

    def test_typed_verification_accepts_exact_payloads(self) -> None:
        packet = self.packet()
        verification = verify_module_workbench_execution_packet_value(packet)
        self.assertTrue(verification.accepted)
        self.assertEqual(verification.artifact_count, packet.artifact_count)
        self.assertEqual(verification.present_count, packet.artifact_count)
        self.assertEqual(verification.missing_count, 0)
        object.__setattr__(packet.artifacts[0], "payload", "tampered")
        tampered = verify_module_workbench_execution_packet_value(packet)
        self.assertFalse(tampered.accepted)
        self.assertTrue(any(not item.passed for item in tampered.checks))

    def test_write_verify_and_load_are_byte_stable(self) -> None:
        packet = self.packet()
        path = self.write_packet(packet)
        verification = verify_module_workbench_execution_packet(path)
        self.assertTrue(verification.accepted)
        self.assertEqual(verification.artifact_count, packet.artifact_count)
        loaded = load_module_workbench_execution_packet(path)
        self.assertEqual(loaded.content_address, packet.content_address)
        self.assertEqual(
            module_workbench_execution_packet_json(loaded),
            module_workbench_execution_packet_json(packet),
        )
        self.assertEqual(
            module_workbench_execution_packet_csv(loaded),
            module_workbench_execution_packet_csv(packet),
        )

    def test_manifest_is_canonical_and_contains_no_payloads(self) -> None:
        packet = self.packet()
        path = self.write_packet(packet)
        raw = (path / MODULE_WORKBENCH_EXECUTION_PACKET_MANIFEST).read_text(encoding="utf-8")
        parsed = json.loads(raw)
        self.assertEqual(raw, json.dumps(parsed, sort_keys=True, separators=(",", ":")) + "\n")
        self.assertNotIn('"payload"', raw)
        self.assertEqual(parsed["artifact_count"], packet.artifact_count)
        self.assertEqual(parsed["content_address"], packet.content_address)

    def test_query_exposes_every_offline_resource(self) -> None:
        packet = self.packet()
        for resource, expected in (
            ("manifest", 1),
            ("artifacts", packet.artifact_count),
            ("checks", len(packet.checks)),
            ("links", 9),
            ("summary", 1),
        ):
            result = query_module_workbench_execution_packet(packet, resource=resource)
            self.assertEqual(result["total"], expected)
            self.assertTrue(result["accepted"])
            self.assertTrue(result["content_address"])

    def test_query_filters_and_paging_are_deterministic(self) -> None:
        packet = self.packet()
        artifacts = query_module_workbench_execution_packet(
            packet,
            resource="artifacts",
            artifact_id="ledger",
        )
        self.assertEqual(artifacts["total"], 1)
        self.assertEqual(artifacts["items"][0]["artifact_id"], "ledger")
        checks = query_module_workbench_execution_packet(
            packet,
            resource="checks",
            plane="linkage",
            passed=True,
            offset=1,
            limit=2,
        )
        self.assertEqual(checks["total"], 5)
        self.assertEqual(len(checks["items"]), 2)
        links = query_module_workbench_execution_packet(
            packet,
            resource="links",
            link_name="runtime",
        )
        self.assertEqual(links["items"][0]["name"], "runtime")
        with self.assertRaises(ValidationError):
            query_module_workbench_execution_packet(packet, resource="unknown")
        with self.assertRaises(ValidationError):
            query_module_workbench_execution_packet(packet, limit=513)
        with self.assertRaises(ValidationError):
            query_module_workbench_execution_packet(packet, offset=-1)

    def test_query_can_load_verified_directory(self) -> None:
        packet = self.packet()
        path = self.write_packet(packet)
        result = query_module_workbench_execution_packet(path, resource="summary")
        self.assertEqual(result["items"][0]["packet_id"], packet.packet_id)
        self.assertEqual(result["items"][0]["artifact_count"], 13)

    def test_replay_returns_accepted_receipts_for_typed_and_filesystem_inputs(self) -> None:
        packet = self.packet()
        typed = replay_module_workbench_execution_packet(packet)
        self.assertTrue(typed["accepted"])
        self.assertEqual(typed["artifact_count"], packet.artifact_count)
        path = self.write_packet(packet)
        persisted = replay_module_workbench_execution_packet(path)
        self.assertTrue(persisted["accepted"])
        self.assertEqual(persisted["packet_address"], packet.content_address)
        self.assertEqual(persisted["replayed_artifacts"], typed["replayed_artifacts"])

    def test_tampered_bytes_and_unlisted_files_are_blocked(self) -> None:
        packet = self.packet()
        path = self.write_packet(packet)
        ledger = path / "ledger.json"
        ledger.write_text(ledger.read_text(encoding="utf-8") + " ", encoding="utf-8")
        verification = verify_module_workbench_execution_packet(path)
        self.assertFalse(verification.accepted)
        self.assertTrue(any(not item.passed for item in verification.checks))

        clean_path = self.write_packet(packet)
        (clean_path / "unlisted.txt").write_text("extra", encoding="utf-8")
        extra_verification = verify_module_workbench_execution_packet(clean_path)
        self.assertFalse(extra_verification.accepted)
        with self.assertRaises(ValidationError):
            load_module_workbench_execution_packet(clean_path)

    def test_missing_artifact_is_blocked_without_crashing(self) -> None:
        packet = self.packet()
        path = self.write_packet(packet)
        (path / "events.csv").unlink()
        verification = verify_module_workbench_execution_packet(path)
        self.assertFalse(verification.accepted)
        self.assertEqual(verification.missing_count, 1)
        self.assertTrue(
            any(
                check.check_id == "artifact-presence" and not check.passed
                for check in verification.checks
            )
        )

    def test_diff_same_packet_is_all_unchanged(self) -> None:
        packet = self.packet()
        diff = diff_module_workbench_execution_packets(packet, packet)
        self.assertEqual(diff["added_artifact_ids"], ())
        self.assertEqual(diff["removed_artifact_ids"], ())
        self.assertEqual(diff["changed_artifact_ids"], ())
        self.assertEqual(len(diff["unchanged_artifact_ids"]), packet.artifact_count)
        self.assertFalse(diff["state_changed"])
        self.assertTrue(diff["accepted"])

    def test_diff_detects_a_replayed_ledger_change(self) -> None:
        base = self.packet()
        ready = next(
            item for item in base.to_dict()["artifacts"] if item["artifact_id"] == "ledger"
        )
        self.assertEqual(ready["kind"], "ledger")
        report = self.fixture.report()
        task = next(item for item in report.tasks)
        changed = build_module_workbench_execution_packet(
            report,
            commands=(execution_command(task.task_id, "skip", "deferred in this snapshot"),),
        )
        diff = diff_module_workbench_execution_packets(base, changed)
        self.assertIn("ledger", diff["changed_artifact_ids"])
        self.assertIn("review", diff["changed_artifact_ids"])
        self.assertTrue(diff["acceptance_changed"] is False)

    def test_release_accepts_packet_and_exposes_threshold_failures(self) -> None:
        packet = self.packet()
        release = build_module_workbench_execution_packet_release(packet)
        verify_module_workbench_execution_packet_release(release)
        self.assertTrue(release.accepted)
        self.assertEqual(release.state, ModuleWorkbenchExecutionPacketReleaseState.ACCEPTED)
        self.assertEqual(release.failed_check_count, 0)
        summary = query_module_workbench_execution_packet_release(release, resource="summary")
        self.assertEqual(summary["total"], 1)
        checks = query_module_workbench_execution_packet_release(
            release,
            resource="checks",
            passed=True,
            limit=32,
        )
        self.assertEqual(checks["total"], release.check_count)

        blocked = build_module_workbench_execution_packet_release(
            packet,
            minimum_artifact_count=99,
        )
        self.assertFalse(blocked.accepted)
        self.assertEqual(blocked.state, ModuleWorkbenchExecutionPacketReleaseState.BLOCKED)
        self.assertTrue(any(not check.passed for check in blocked.checks))

    def test_release_can_verify_a_persisted_packet(self) -> None:
        packet = self.packet()
        path = self.write_packet(packet)
        release = build_module_workbench_execution_packet_release(path)
        self.assertTrue(release.accepted)
        self.assertEqual(release.packet_address, packet.content_address)
        verify_module_workbench_execution_packet_release(release)

    def test_release_exports_are_stable_and_public(self) -> None:
        release = build_module_workbench_execution_packet_release(self.packet())
        self.assertIn('"release_id"', module_workbench_execution_packet_release_json(release))
        self.assertIn("check_id", module_workbench_execution_packet_release_csv(release))
        self.assertIn(
            "Packet Release", render_module_workbench_execution_packet_release_markdown(release)
        )
        self.assertTrue(module_workbench_execution_packet_release_schema()["identity_free"])
        self.assertEqual(
            module_workbench_execution_packet_release_capabilities()["operation_count"],
            len(module_workbench_execution_packet_release_capabilities()["operations"]),
        )

    def test_packet_exports_schema_and_capabilities(self) -> None:
        packet = self.packet()
        self.assertIn(
            "Module Workbench Execution Packet",
            render_module_workbench_execution_packet_markdown(packet),
        )
        self.assertEqual(module_workbench_execution_packet_schema()["artifact_count"], 13)
        caps = module_workbench_execution_packet_capabilities()
        self.assertEqual(caps["operation_count"], len(caps["operations"]))
        self.assertTrue(caps["identity_free"])
        query_schema = module_workbench_execution_packet_query_schema()
        self.assertEqual(
            query_schema["resources"], ["manifest", "artifacts", "checks", "links", "summary"]
        )
        query_caps = module_workbench_execution_packet_query_capabilities()
        self.assertEqual(query_caps["operation_count"], len(query_caps["operations"]))

    def test_runtime_runs_in_memory_in_declared_stage_order(self) -> None:
        runtime = run_module_workbench_execution_packet_runtime(self.fixture.report())
        verify_module_workbench_execution_packet_runtime(runtime)
        self.assertTrue(runtime.accepted)
        self.assertEqual(runtime.stage_count, 7)
        self.assertEqual(runtime.completed_count, 7)
        self.assertEqual(
            tuple(stage.kind for stage in runtime.stages),
            tuple(ModuleWorkbenchExecutionPacketRuntimeStageKind),
        )
        self.assertEqual(
            query_module_workbench_execution_packet_runtime(runtime, resource="summary")["total"],
            1,
        )
        self.assertEqual(
            len(
                query_module_workbench_execution_packet_runtime(runtime, resource="stages")["items"]
            ),
            7,
        )

    def test_runtime_writes_and_rechecks_a_packet_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "packet"
            runtime = run_module_workbench_execution_packet_runtime(
                self.fixture.report(),
                destination=destination,
            )
            self.assertTrue(runtime.accepted)
            self.assertTrue((destination / MODULE_WORKBENCH_EXECUTION_PACKET_MANIFEST).exists())
            self.assertTrue(all(stage.accepted for stage in runtime.stages))
            self.assertIn("packet_address", module_workbench_execution_packet_runtime_json(runtime))
            self.assertIn("kind", module_workbench_execution_packet_runtime_csv(runtime))
            self.assertTrue(module_workbench_execution_packet_runtime_schema()["identity_free"])
            caps = module_workbench_execution_packet_runtime_capabilities()
            self.assertEqual(caps["operation_count"], len(caps["operations"]))

    def test_runtime_rejects_tampered_stage_address(self) -> None:
        runtime = run_module_workbench_execution_packet_runtime(self.fixture.report())
        object.__setattr__(runtime.stages[0], "detail", "tampered")
        with self.assertRaises(ValidationError):
            verify_module_workbench_execution_packet_runtime(runtime)

    def test_cli_builds_verifies_queries_releases_and_runs_packet(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            packet_dir = root / "packet"
            runtime_dir = root / "runtime-packet"
            packet_output = root / "packet-result.json"
            verify_output = root / "verify.json"
            query_output = root / "query.json"
            release_output = root / "release.json"
            runtime_output = root / "runtime.json"
            common = [
                "--source-root",
                str(self.fixture.package),
                "--test-root",
                str(self.fixture.tests),
                "--docs-root",
                str(self.fixture.docs),
            ]
            self.assertEqual(
                main(
                    [
                        "module-workbench-execution-packet",
                        *common,
                        "--capacity",
                        "5",
                        "--max-tasks-per-module",
                        "2",
                        "--destination",
                        str(packet_dir),
                        "--format",
                        "summary",
                        "--output",
                        str(packet_output),
                    ]
                ),
                0,
            )
            self.assertTrue(json.loads(packet_output.read_text(encoding="utf-8"))["accepted"])
            self.assertEqual(
                main(
                    [
                        "module-workbench-execution-packet-verify",
                        str(packet_dir),
                        "--output",
                        str(verify_output),
                    ]
                ),
                0,
            )
            self.assertTrue(json.loads(verify_output.read_text(encoding="utf-8"))["accepted"])
            self.assertEqual(
                main(
                    [
                        "module-workbench-execution-packet-query",
                        str(packet_dir),
                        "--resource",
                        "links",
                        "--output",
                        str(query_output),
                    ]
                ),
                0,
            )
            self.assertEqual(json.loads(query_output.read_text(encoding="utf-8"))["total"], 9)
            self.assertEqual(
                main(
                    [
                        "module-workbench-execution-packet-release",
                        str(packet_dir),
                        "--format",
                        "summary",
                        "--output",
                        str(release_output),
                    ]
                ),
                0,
            )
            self.assertTrue(json.loads(release_output.read_text(encoding="utf-8"))["accepted"])
            self.assertEqual(
                main(
                    [
                        "module-workbench-execution-packet-runtime",
                        *common,
                        "--capacity",
                        "5",
                        "--max-tasks-per-module",
                        "2",
                        "--destination",
                        str(runtime_dir),
                        "--resource",
                        "summary",
                        "--output",
                        str(runtime_output),
                    ]
                ),
                0,
            )
            self.assertTrue(json.loads(runtime_output.read_text(encoding="utf-8"))["accepted"])


if __name__ == "__main__":
    unittest.main()
