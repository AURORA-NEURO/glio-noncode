"""Contract tests for cross-history certificate observability and snapshots."""

# ruff: noqa: E501, I001

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from glio_noncode import registry_federation_consensus_gate_certificate_observatory as observatory_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_audit as observatory_audit_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_package as package_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_package_audit as package_audit_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_query_audit as query_audit_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_report as report_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_report_audit as report_audit_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_diff as diff_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_diff_audit as diff_audit_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_diff_query_audit as diff_query_audit_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_runtime as runtime_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_runtime_audit as runtime_audit_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_replay as replay_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_replay_audit as replay_audit_model
from glio_noncode import registry_federation_consensus_gate_certificate_history as history_model
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from tests.test_registry_federation_consensus_gate_certificate import CertificateFixture


class CertificateObservatoryTests(CertificateFixture):
    """Exercise the complete observatory graph from typed histories to HTTP."""

    def _histories(self, root: Path):
        issued = self.certificate_runtime(root / "issued", "primary", "replica")
        withheld = self.certificate_runtime(root / "withheld", "primary", "held")
        first = history_model.build_history(((issued.certificate, issued.certificate_audit),), history_id="issued-history")
        second = history_model.build_history(((withheld.certificate, withheld.certificate_audit),), history_id="withheld-history")
        return first, second

    def _graph(self, root: Path):
        first, second = self._histories(root)
        observatory = observatory_model.build_observatory((first, second), observatory_id="certificate-observatory")
        observatory_audit = observatory_audit_model.audit_observatory(observatory)
        query = observatory_model.query_observatory(observatory, resources=observatory_model.RESOURCES, limit=100)
        query_audit = query_audit_model.audit_query(query)
        report = report_model.build_report(observatory, report_id="certificate-health-report")
        report_audit = report_audit_model.audit_report(report)
        package = package_model.build_package(observatory, query=query, report=report, observatory_audit=observatory_audit, query_audit=query_audit, report_audit=report_audit, package_id="certificate-observatory-package")
        package_audit = package_audit_model.audit_package(package)
        return observatory, observatory_audit, query, query_audit, report, report_audit, package, package_audit

    def test_observatory_conserves_history_streams_and_addresses(self):
        with tempfile.TemporaryDirectory() as temporary:
            value, audit, _, _, _, _, _, _ = self._graph(Path(temporary))
            self.assertTrue(audit.accepted)
            self.assertEqual((value.history_count, value.observation_count), (2, 2))
            self.assertEqual((value.issued_count, value.withheld_count), (1, 1))
            self.assertEqual((value.accepted_count, value.held_count), (1, 1))
            self.assertEqual(tuple(item.ordinal for item in value.observations), (1, 2))
            self.assertEqual(tuple(item.history_id for item in value.observations), ("issued-history", "withheld-history"))
            self.assertEqual(value.total_failed_count, value.observations[1].failed_count)
            self.assertTrue(value.content_address.startswith(observatory_model.OBSERVATORY_PREFIX + ":"))
            self.assertEqual(observatory_model.observatory_from_mapping(value.to_dict()).to_dict(), value.to_dict())
            self.assertEqual(observatory_audit_model.audit_from_mapping(audit.to_dict()).to_dict(), audit.to_dict())
            self.assertEqual(tuple(item.check_id for item in audit.checks), observatory_audit_model.CHECK_IDS)

    def test_query_resources_filters_and_pagination_are_bounded(self):
        with tempfile.TemporaryDirectory() as temporary:
            value, _, full, full_audit, _, _, _, _ = self._graph(Path(temporary))
            self.assertTrue(full_audit.accepted)
            self.assertEqual(full.total_count, 9)
            self.assertEqual(full.matched_count, 9)
            self.assertEqual(full.returned_count, 9)
            self.assertFalse(full.truncated)
            self.assertEqual(full.rows[0].resource, "summary")
            self.assertEqual(full.rows[-1].resource, "evidence")
            page = observatory_model.query_observatory(value, resources=("observations", "withheld"), history_id="withheld-history", accepted=False, offset=0, limit=1)
            self.assertEqual((page.total_count, page.matched_count, page.returned_count), (3, 2, 1))
            self.assertTrue(page.truncated)
            self.assertEqual(page.next_offset, 1)
            self.assertEqual(page.rows[0].history_id, "withheld-history")
            self.assertEqual(page.rows[0].ordinal, 1)
            with self.assertRaises(ValidationError):
                observatory_model.query_observatory(value, resources=("unsupported",))
            with self.assertRaises(ValidationError):
                observatory_model.query_observatory(value, resources=("observations",), state="unknown")

    def test_health_report_exposes_trend_counters_and_alerts(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, _, _, _, report, report_audit, _, _ = self._graph(Path(temporary))
            self.assertTrue(report_audit.accepted)
            self.assertEqual((report.observation_count, report.issued_count, report.withheld_count), (2, 1, 1))
            self.assertEqual(report.acceptance_ratio, 0.5)
            self.assertEqual(report.latest_state, "withheld")
            self.assertEqual(report.latest_decision, "hold")
            self.assertEqual(report.consecutive_withheld_count, 1)
            self.assertEqual(report.stream_state, "held")
            self.assertGreaterEqual(report.alert_count, 2)
            self.assertEqual(report.alert_count, len(report.alerts))
            self.assertEqual(report_model.report_from_mapping(report.to_dict()).to_dict(), report.to_dict())
            self.assertEqual(report_audit_model.audit_from_mapping(report_audit.to_dict()).to_dict(), report_audit.to_dict())
            self.assertEqual(tuple(item.check_id for item in report_audit.checks), report_audit_model.CHECK_IDS)

    def test_exact_eight_file_package_replays_and_audits(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, _, _, _, _, _, package, package_audit = self._graph(root)
            self.assertTrue(package_audit.accepted)
            self.assertEqual(package_model.FILES, ("manifest.json", "package.json", "observatory.json", "query.json", "report.json", "observatory-audit.json", "query-audit.json", "report-audit.json"))
            destination = root / "package"
            package_model.write_package(package, destination)
            self.assertEqual({item.name for item in destination.iterdir()}, set(package_model.FILES))
            loaded = package_model.load_package(destination)
            self.assertEqual(loaded.to_dict(), package.to_dict())
            self.assertEqual(package_model.package_bytes(package), {name: (destination / name).read_bytes() for name in package_model.FILES})
            self.assertEqual(package_audit_model.audit_package(loaded).to_dict(), package_audit.to_dict())
            with self.assertRaises(ValidationError):
                package_model.write_package(package, destination)
            package_model.write_package(package, destination, overwrite=True)
            (destination / "extra.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(ValidationError):
                package_model.load_package(destination)

    def test_public_schemas_are_closed_and_exports_are_path_free(self):
        with tempfile.TemporaryDirectory() as temporary:
            value, _, query, _, report, _, package, _ = self._graph(Path(temporary))
            schemas = (observatory_model.observatory_schema(), observatory_model.query_schema(), observatory_model.row_schema(), observatory_model.result_schema(), observatory_audit_model.audit_schema(), query_audit_model.audit_schema(), report_model.alert_schema(), report_model.report_schema(), report_audit_model.audit_schema(), package_model.manifest_schema(), package_model.package_schema(), package_audit_model.audit_schema())
            for schema in schemas:
                self.assertFalse(schema["additionalProperties"])
                self.assertEqual(set(schema["required"]), set(schema["properties"]))
            encoded = " ".join((observatory_model.observatory_json(value), observatory_model.query_json(query), report_model.report_json(report), package_model.package_json(package)))
            self.assertNotIn("C:\\Users\\", encoded)
            self.assertNotIn("/home/", encoded)
            self.assertNotIn('"agent"', encoded)
            self.assertNotIn('"language"', encoded)

    def test_cli_builds_queries_reports_packages_and_audits(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first, second = self._histories(root)
            first_dir = root / "first-history"
            second_dir = root / "second-history"
            history_model.write_history(first, first_dir)
            history_model.write_history(second, second_dir)
            observatory_json = root / "observatory.json"
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(main(["registry-federation-consensus-gate-certificate-observatory", "--input", str(first_dir), "--input", str(second_dir), "--output", str(observatory_json), "--format", "json"]), 0)
            observatory = observatory_model.observatory_from_mapping(json.loads(observatory_json.read_text(encoding="utf-8")))
            self.assertEqual(observatory.observation_count, 2)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(main(["registry-federation-consensus-gate-certificate-observatory-audit", "--input", str(observatory_json), "--format", "summary"]), 0)
            self.assertEqual(json.loads(output.getvalue())["passed_count"], len(observatory_audit_model.CHECK_IDS))
            query_json = root / "query.json"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["registry-federation-consensus-gate-certificate-observatory-query", "--input", str(observatory_json), "--resource", "withheld", "--limit", "1", "--output", str(query_json), "--format", "json"]), 0)
            query = observatory_model.query_from_mapping(json.loads(query_json.read_text(encoding="utf-8")))
            self.assertEqual(query.returned_count, 1)
            report_json = root / "report.json"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["registry-federation-consensus-gate-certificate-observatory-report", "--input", str(observatory_json), "--output", str(report_json), "--format", "json"]), 0)
            report = report_model.report_from_mapping(json.loads(report_json.read_text(encoding="utf-8")))
            self.assertEqual(report.observation_count, 2)
            package_dir = root / "package"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["registry-federation-consensus-gate-certificate-observatory-package", "--input", str(observatory_json), "--destination", str(package_dir), "--format", "summary"]), 0)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(main(["registry-federation-consensus-gate-certificate-observatory-package-audit", "--input", str(package_dir), "--format", "summary"]), 0)
            self.assertEqual(json.loads(output.getvalue())["passed_count"], len(package_audit_model.CHECK_IDS))

    def test_http_routes_return_observatory_query_report_and_package_contracts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first, second = self._histories(root)
            first_dir, second_dir = root / "first-history", root / "second-history"
            history_model.write_history(first, first_dir)
            history_model.write_history(second, second_dir)
            observatory = observatory_model.build_observatory((first, second), observatory_id="http-observatory")
            source = root / "observatory.json"
            source.write_text(observatory_model.observatory_json(observatory), encoding="utf-8")
            reversed_source = root / "observatory-reversed.json"
            reversed_source.write_text(observatory_model.observatory_json(observatory_model.build_observatory((second, first), observatory_id="http-reversed")), encoding="utf-8")
            server = create_server("127.0.0.1", 0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = f"http://127.0.0.1:{server.server_port}/v1/registry/federation/consensus/gate/certificate/observatory"
                schemas = ("/schema", "/query/schema", "/query/row-schema", "/query/result-schema", "/audit/schema", "/query-audit/schema", "/report/schema", "/report/audit/schema", "/package/schema", "/package/audit/schema", "/diff/schema", "/diff/audit/schema", "/diff/query/schema", "/diff/query-audit/schema", "/runtime/schema", "/runtime/audit/schema", "/capabilities")
                for suffix in schemas:
                    with urlopen(base + suffix, timeout=10) as response:
                        self.assertEqual(response.status, 200)
                        self.assertIsInstance(json.loads(response.read()), dict)
                query = urlencode({"input": str(source), "resource": "withheld", "limit": "1", "format": "json"})
                with urlopen(base + "/query?" + query, timeout=10) as response:
                    self.assertEqual(json.loads(response.read())["returned_count"], 1)
                with urlopen(base + "/report?" + urlencode({"input": str(source), "format": "summary"}), timeout=10) as response:
                    self.assertEqual(json.loads(response.read())["observation_count"], 2)
                with urlopen(base + "/audit?" + urlencode({"input": str(source), "format": "summary"}), timeout=10) as response:
                    self.assertEqual(json.loads(response.read())["passed_count"], len(observatory_audit_model.CHECK_IDS))
                with urlopen(base + "/diff?" + urlencode({"left": str(source), "right": str(reversed_source), "format": "summary"}), timeout=10) as response:
                    self.assertEqual(json.loads(response.read())["changed_count"], 2)
                runtime_query = urlencode((("input", str(first_dir)), ("input", str(second_dir)), ("destination", str(root / "http-runtime")), ("format", "summary")))
                with urlopen(base + "/runtime?" + runtime_query, timeout=10) as response:
                    self.assertTrue(json.loads(response.read())["persisted"])
                replay_package = root / "http-runtime"
                with urlopen(base + "/replay?" + urlencode({"input": str(replay_package), "format": "summary"}), timeout=10) as response:
                    self.assertTrue(json.loads(response.read())["byte_equal"])
                replay_source = root / "replay.json"
                replay_source.write_text(replay_model.replay_json(replay_model.replay_package(replay_package)), encoding="utf-8")
                with urlopen(base + "/replay/audit?" + urlencode({"input": str(replay_source), "format": "summary"}), timeout=10) as response:
                    self.assertEqual(json.loads(response.read())["passed_count"], len(replay_audit_model.CHECK_IDS))
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_observatory_diff_tracks_logical_transitions_and_deltas(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first, second = self._histories(root)
            left = observatory_model.build_observatory((first, second), observatory_id="left-observatory")
            right = observatory_model.build_observatory((second, first), observatory_id="right-observatory")
            value = diff_model.build_diff(left, right, diff_id="transition-diff")
            audit = diff_audit_model.audit_diff(value)
            query = diff_model.query_diff(value, resources=("items", "changed"), action="changed", limit=100)
            query_audit = diff_query_audit_model.audit_query(query)
            self.assertTrue(audit.accepted)
            self.assertTrue(query_audit.accepted)
            self.assertEqual((value.item_count, value.changed_count, value.added_count, value.removed_count), (2, 2, 0, 0))
            self.assertEqual(value.direction, "mixed")
            self.assertEqual(query.returned_count, 4)
            self.assertEqual({row.resource for row in query.rows}, {"items", "changed"})
            self.assertEqual(audit.passed_count, len(diff_audit_model.CHECK_IDS))
            self.assertEqual(query_audit.passed_count, len(diff_query_audit_model.CHECK_IDS))
            self.assertEqual(diff_model.diff_from_mapping(value.to_dict()).to_dict(), value.to_dict())
            self.assertEqual(diff_model.query_from_mapping(query.to_dict()).to_dict(), query.to_dict())
            self.assertIn("accepted delta", diff_model.render_diff_markdown(value).lower())

    def test_observatory_diff_rejects_tampered_deltas_and_queries_are_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            first, second = self._histories(Path(temporary))
            left = observatory_model.build_observatory((first, second), observatory_id="tamper-left")
            right = observatory_model.build_observatory((first,), observatory_id="tamper-right")
            value = diff_model.build_diff(left, right)
            corrupted = value.to_dict()
            corrupted["accepted_delta"] = 1
            with self.assertRaises(ValidationError):
                diff_model.diff_from_mapping(corrupted)
            with self.assertRaises(ValidationError):
                diff_model.query_diff(value, resources=("missing",))
            for schema in (diff_model.item_schema(), diff_model.diff_schema(), diff_model.query_schema(), diff_model.row_schema(), diff_model.result_schema(), diff_audit_model.audit_schema(), diff_query_audit_model.audit_schema()):
                self.assertFalse(schema["additionalProperties"])

    def test_observatory_runtime_orchestrates_persistence_and_replay(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first, second = self._histories(root)
            first_dir, second_dir = root / "first", root / "second"
            history_model.write_history(first, first_dir)
            history_model.write_history(second, second_dir)
            destination = root / "runtime-package"
            value = runtime_model.run_runtime((first_dir, second_dir), runtime_id="observatory-runtime", destination=destination, limit=20)
            audit = runtime_audit_model.audit_runtime(value)
            self.assertTrue(value.persisted)
            self.assertTrue(value.package_address)
            self.assertTrue(audit.accepted)
            self.assertEqual(audit.passed_count, len(runtime_audit_model.CHECK_IDS))
            self.assertEqual(runtime_model.runtime_from_mapping(value.to_dict()).to_dict(), value.to_dict())
            self.assertEqual(runtime_model.runtime_json(value), runtime_model.runtime_json(runtime_model.runtime_from_mapping(value.to_dict())))
            with self.assertRaises(ValidationError):
                runtime_model.run_runtime((), runtime_id="empty-runtime")

    def test_diff_and_runtime_schema_capabilities_are_cli_callable(self):
        commands = (
            "registry-federation-consensus-gate-certificate-observatory-diff-schema",
            "registry-federation-consensus-gate-certificate-observatory-diff-audit-schema",
            "registry-federation-consensus-gate-certificate-observatory-diff-query-schema",
            "registry-federation-consensus-gate-certificate-observatory-diff-query-audit-schema",
            "registry-federation-consensus-gate-certificate-observatory-runtime-schema",
            "registry-federation-consensus-gate-certificate-observatory-runtime-audit-schema",
            "registry-federation-consensus-gate-certificate-observatory-replay-schema",
            "registry-federation-consensus-gate-certificate-observatory-replay-audit-schema",
        )
        for command in commands:
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(main([command]), 0)
            self.assertFalse(json.loads(output.getvalue())["additionalProperties"])

    def test_replay_receipt_proves_exact_package_bytes_and_audit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            graph = self._graph(root)
            destination = root / "replay-package"
            package_model.write_package(graph[6], destination)
            replay = replay_model.replay_package(destination)
            audit = replay_audit_model.audit_replay(replay)
            self.assertTrue(replay.byte_equal)
            self.assertTrue(replay.projection_equal)
            self.assertTrue(replay.audit_accepted)
            self.assertEqual(replay.member_count, 8)
            self.assertEqual(replay.members, package_model.FILES)
            self.assertTrue(audit.accepted)
            self.assertEqual(audit.passed_count, len(replay_audit_model.CHECK_IDS))
            self.assertEqual(replay_model.replay_from_mapping(replay.to_dict()).to_dict(), replay.to_dict())
            self.assertEqual(replay_audit_model.audit_from_mapping(audit.to_dict()).to_dict(), audit.to_dict())
            self.assertIn("byte equal", replay_model.render_replay_markdown(replay).lower())

    def test_replay_receipt_and_audit_schemas_are_closed(self):
        for schema in (replay_model.replay_schema(), replay_audit_model.check_schema(), replay_audit_model.audit_schema()):
            self.assertFalse(schema["additionalProperties"])
            self.assertEqual(set(schema["required"]), set(schema["properties"]))

    def test_cli_runtime_and_replay_commands_create_auditable_handoff(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first, second = self._histories(root)
            first_dir, second_dir = root / "cli-first", root / "cli-second"
            history_model.write_history(first, first_dir)
            history_model.write_history(second, second_dir)
            runtime_json = root / "runtime.json"
            package_dir = root / "runtime-package"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["registry-federation-consensus-gate-certificate-observatory-runtime", "--input", str(first_dir), "--input", str(second_dir), "--destination", str(package_dir), "--format", "json", "--output", str(runtime_json)]), 0)
            runtime = runtime_model.runtime_from_mapping(json.loads(runtime_json.read_text(encoding="utf-8")))
            self.assertTrue(runtime.persisted)
            self.assertEqual(runtime.observatory.observation_count, 2)
            replay_json = root / "replay.json"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["registry-federation-consensus-gate-certificate-observatory-replay", "--input", str(package_dir), "--format", "json", "--output", str(replay_json)]), 0)
            replay = replay_model.replay_from_mapping(json.loads(replay_json.read_text(encoding="utf-8")))
            self.assertTrue(replay.byte_equal)
            self.assertTrue(replay.projection_equal)
            audit_json = root / "replay-audit.json"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["registry-federation-consensus-gate-certificate-observatory-replay-audit", "--input", str(replay_json), "--format", "json", "--output", str(audit_json)]), 0)
            audit = replay_audit_model.audit_from_mapping(json.loads(audit_json.read_text(encoding="utf-8")))
            self.assertTrue(audit.accepted)
            self.assertEqual(audit.passed_count, len(replay_audit_model.CHECK_IDS))

    def test_replay_rejects_member_drift_before_emitting_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            graph = self._graph(root)
            destination = root / "drifted-package"
            package_model.write_package(graph[6], destination)
            (destination / "unexpected.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(ValidationError):
                replay_model.replay_package(destination)


if __name__ == "__main__":
    unittest.main()
