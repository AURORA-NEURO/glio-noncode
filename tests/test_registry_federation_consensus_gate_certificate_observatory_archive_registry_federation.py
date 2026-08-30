"""Deep contract tests for independent archive-registry federation analysis.

The fixtures use the repository's downloaded package shape, while the tests
exercise peer reconciliation, evidence queries, diffs, quorum, reports,
runtime replay, CLI, HTTP, and public-data boundaries.
"""

# ruff: noqa: E501, I001

from __future__ import annotations

import contextlib
import io
import json
import shutil
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive as archive_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry as registry_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation as federation_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_audit as federation_audit_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_consensus as consensus_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_consensus_audit as consensus_audit_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_diff as diff_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_diff_audit as diff_audit_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_diff_query as diff_query_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_diff_query_audit as diff_query_audit_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_query as query_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_query_audit as query_audit_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_report as report_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_report_audit as report_audit_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_runtime as runtime_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_runtime_audit as runtime_audit_model
from glio_noncode.api import create_server
from glio_noncode.cli import build_parser, main
from glio_noncode.errors import ValidationError
from tests import test_registry_federation_consensus_gate_certificate_observatory_archive as source_archive_tests


class ArchiveRegistryFederationContractTests(unittest.TestCase):
    """Run each public contract against one cached package-shaped fixture."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.source_fixture = source_archive_tests.CertificateObservatoryArchiveTests("runTest")
        cls.source_fixture.setUp()
        cls.fixture_root = Path(tempfile.mkdtemp(prefix="glio-noncode-federation-fixture-"))
        cls.fixture_package = cls.source_fixture._package(cls.fixture_root / "package", package_id="downloaded-observatory-package")

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.fixture_root, ignore_errors=True)
        cls.source_fixture.tearDown()

    def package(self, root: Path | None = None, package_id: str = "downloaded-observatory-package"):
        return self.fixture_package

    def archive(self, root: Path, archive_id: str):
        return archive_model.build_archive(self.package(root), archive_id=archive_id)

    def registry(self, root: Path, *archive_ids: str, registry_id: str = "downloaded-observatory-registry"):
        archives = tuple(self.archive(root / "archives", archive_id) for archive_id in archive_ids)
        return registry_model.build_registry_from_archives(archives, entry_ids=tuple("entry-" + item for item in archive_ids), registry_id=registry_id)

    def persist_registry(self, value, destination: Path) -> Path:
        registry_model.write_registry(value, destination)
        return destination

    def persist_federation(self, value, destination: Path) -> Path:
        destination.write_text(federation_model.federation_json(value), encoding="utf-8")
        return destination

    def pair(self, root: Path):
        return (self.registry(root / "left", "shared-a", "shared-b", registry_id="left-registry"), self.registry(root / "right", "shared-a", "shared-b", registry_id="right-registry"))

    def federation(self, root: Path, *, divergent: bool = False):
        if not divergent:
            values = self.pair(root)
        else:
            package = self.package(root, "divergent-package")
            left_archive = archive_model.build_archive(package, archive_id="divergent-archive-left")
            right_archive = archive_model.build_archive(package, archive_id="divergent-archive-right")
            left_entry = registry_model.entry_from_archive(left_archive, entry_id="divergent-entry")
            right_entry = registry_model.entry_from_archive(right_archive, entry_id="divergent-entry")
            values = (registry_model.build_registry((left_entry,), registry_id="left-registry"), registry_model.build_registry((right_entry,), registry_id="right-registry"))
        return federation_model.build_federation(values, peer_ids=("alpha", "beta"), federation_id="downloaded-registry-federation")

    def assert_public(self, value: object) -> None:
        raw = value.to_dict() if hasattr(value, "to_dict") else value
        encoded = json.dumps(raw, sort_keys=True, default=list).lower()
        for forbidden in ("local_path", "generated_by", "agent", "assistant", "language", "private_key", "secret", "token"):
            self.assertNotIn(forbidden, encoded)

    def assert_closed(self, schema: dict[str, object]) -> None:
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(set(schema["required"]), set(schema["properties"]))

    def test_consistent_peers_preserve_identity_and_two_sided_entry_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.federation(Path(temporary))
            self.assertEqual(value.peer_count, 2)
            self.assertEqual(value.observation_count, 2)
            self.assertEqual((value.consistent_count, value.divergent_count, value.missing_count, value.conflict_count), (2, 0, 0, 0))
            self.assertEqual(tuple(item.peer_id for item in value.peers), ("alpha", "beta"))
            self.assertTrue(all(item.state == "consistent" and item.presence_count == 2 for item in value.observations))
            self.assertTrue(all(len(item.observed_archive_addresses) == 2 for item in value.observations))
            self.assertEqual(value.content_address, federation_model.address_federation(value))
            self.assert_public(value)

    def test_default_order_is_stable_and_federation_mapping_replays(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first, second = self.pair(root)
            forward = federation_model.build_federation((first, second), federation_id="order-stable")
            reverse = federation_model.build_federation((second, first), federation_id="order-stable")
            self.assertEqual(forward.to_dict(), reverse.to_dict())
            self.assertEqual(federation_model.federation_from_mapping(forward.to_dict()).to_dict(), forward.to_dict())
            altered = json.loads(federation_model.federation_json(forward))
            altered["content_address"] = "wrong:federation"
            with self.assertRaises(ValidationError):
                federation_model.federation_from_mapping(altered)

    def test_missing_and_divergent_observations_are_not_collapsed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            shared = self.registry(root / "shared", "shared", registry_id="shared-registry")
            extra = self.registry(root / "extra", "shared", "only-left", registry_id="extra-registry")
            missing = federation_model.build_federation((shared, extra), peer_ids=("one", "two"))
            self.assertEqual(missing.missing_count, 1)
            self.assertEqual(missing.observation("entry-only-left").state, "missing")
            divergent = self.federation(root / "divergent", divergent=True)
            self.assertEqual(divergent.divergent_count, 1)
            self.assertEqual(divergent.missing_count, 0)
            self.assertEqual(divergent.observations[0].state, "divergent")
            self.assertGreaterEqual(divergent.conflict_count, 1)

    def test_every_federation_audit_check_passes_and_replays(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.federation(Path(temporary))
            audit = federation_audit_model.audit_federation(value)
            self.assertTrue(audit.accepted)
            self.assertEqual(audit.failed_count, 0)
            self.assertEqual(tuple(item.check_id for item in audit.checks), federation_audit_model.CHECK_IDS)
            self.assertEqual(federation_audit_model.audit_from_mapping(audit.to_dict()).to_dict(), audit.to_dict())
            self.assertIn("check_id", federation_audit_model.audit_csv(audit))
            self.assertIn("Accepted", federation_audit_model.render_audit_markdown(audit))
            self.assert_public(audit)

    def test_query_resources_filters_and_page_ordinals_are_conserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.federation(Path(temporary))
            result = query_model.query_federation(value, resources=query_model.RESOURCES, limit=100)
            self.assertEqual((result.total_count, result.matched_count, result.returned_count), (5, 5, 5))
            self.assertEqual(tuple(row.ordinal for row in result.rows), (1, 2, 3, 4, 5))
            self.assertEqual(tuple(row.resource for row in result.rows), ("summary", "peers", "peers", "observations", "observations"))
            self.assertTrue(query_audit_model.audit_query(result).accepted)
            page = query_model.query_federation(value, resources=("observations",), state="consistent", offset=1, limit=1)
            self.assertEqual((page.matched_count, page.returned_count, page.next_offset, page.rows[0].ordinal), (2, 1, 2, 2))
            self.assertTrue(page.truncated)
            self.assertEqual(query_model.query_federation(value, resources=("observations",), entry_id=value.observations[0].entry_id, limit=20).matched_count, 1)

    def test_query_and_query_audit_reject_tampered_projection(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = query_model.query_federation(self.federation(Path(temporary)), limit=100)
            self.assertEqual(query_model.query_from_mapping(result.to_dict()).to_dict(), result.to_dict())
            altered = json.loads(query_model.query_json(result))
            altered["rows"][0]["ordinal"] = 99
            with self.assertRaises(ValidationError):
                query_model.query_from_mapping(altered)
            audit = query_audit_model.audit_query(result)
            altered_audit = json.loads(query_audit_model.audit_json(audit))
            altered_audit["content_address"] = "wrong:audit"
            with self.assertRaises(ValidationError):
                query_audit_model.audit_from_mapping(altered_audit)

    def test_quorum_selects_consistent_entries_and_holds_divergent_entries(self):
        with tempfile.TemporaryDirectory() as temporary:
            clean = self.federation(Path(temporary))
            consensus = consensus_model.build_consensus(clean, quorum=2)
            self.assertTrue(consensus.accepted)
            self.assertEqual((consensus.state, consensus.decision, consensus.selected_count, consensus.held_count), ("ready", "accept", 2, 0))
            self.assertTrue(consensus_audit_model.audit_consensus(consensus).accepted)
            blocked = consensus_model.build_consensus(self.federation(Path(temporary) / "blocked", divergent=True), quorum=2)
            self.assertFalse(blocked.accepted)
            self.assertEqual((blocked.state, blocked.decision), ("blocked", "hold"))
            self.assertGreaterEqual(blocked.held_count, 1)
            self.assertTrue(consensus_audit_model.audit_consensus(blocked).accepted)

    def test_diff_categories_and_diff_query_audit_replay(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = self.package(root, "diff-package")
            same_left = archive_model.build_archive(package, archive_id="same-archive")
            same_right = archive_model.build_archive(package, archive_id="same-archive")
            removed = archive_model.build_archive(package, archive_id="removed-archive")
            added = archive_model.build_archive(package, archive_id="added-archive")
            left_registry = registry_model.build_registry_from_archives((same_left, removed), entry_ids=("same-entry", "removed-entry"), registry_id="left")
            right_registry = registry_model.build_registry_from_archives((same_right, added), entry_ids=("same-entry", "added-entry"), registry_id="right")
            left = federation_model.build_federation((left_registry,), peer_ids=("left",), federation_id="left-federation")
            right = federation_model.build_federation((right_registry,), peer_ids=("right",), federation_id="right-federation")
            value = diff_model.build_diff(left, right, diff_id="four-way-diff")
            self.assertEqual((value.added_count, value.removed_count, value.changed_count, value.unchanged_count), (1, 1, 0, 1))
            self.assertTrue(diff_audit_model.audit_diff(value).accepted)
            query = diff_query_model.query_diff(value, resources=diff_query_model.RESOURCES, limit=100)
            self.assertEqual(query.returned_count, query.matched_count)
            self.assertTrue(diff_query_audit_model.audit_query(query).accepted)
            self.assertEqual(diff_query_model.query_from_mapping(query.to_dict()).to_dict(), query.to_dict())

    def test_reports_explain_conflicts_and_clean_runtime_is_ready(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            clean = self.federation(root)
            clean_report = report_model.build_report(clean)
            self.assertTrue(clean_report.accepted)
            self.assertEqual(clean_report.status, "ready")
            self.assertTrue(report_audit_model.audit_report(clean_report).accepted)
            blocked = self.federation(root / "blocked", divergent=True)
            blocked_report = report_model.build_report(blocked)
            self.assertFalse(blocked_report.accepted)
            self.assertEqual(blocked_report.decision, "hold")
            self.assertGreaterEqual(blocked_report.alert_count, 1)
            self.assertTrue(report_audit_model.audit_report(blocked_report).accepted)

    def test_runtime_persists_exact_members_and_rejects_member_tampering(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            left, right = self.pair(root)
            left_dir = self.persist_registry(left, root / "left-registry")
            right_dir = self.persist_registry(right, root / "right-registry")
            destination = root / "runtime"
            value = runtime_model.run_runtime((left_dir, right_dir), peer_ids=("left", "right"), quorum=2, destination=destination, runtime_id="persisted-runtime")
            self.assertTrue(value.accepted)
            self.assertEqual(tuple(sorted(item.name for item in destination.iterdir())), tuple(sorted(runtime_model.FILES)))
            self.assertEqual(runtime_model.load_runtime(destination).to_dict(), value.to_dict())
            self.assertTrue(runtime_audit_model.audit_runtime(value).accepted)
            (destination / "extra.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(ValidationError):
                runtime_model.load_runtime(destination)
            (destination / "extra.json").unlink()
            raw = (destination / runtime_model.FEDERATION_NAME).read_bytes()
            (destination / runtime_model.FEDERATION_NAME).write_bytes(raw + b" ")
            with self.assertRaises(ValidationError):
                runtime_model.load_runtime(destination)

    def test_runtime_accepts_registry_json_and_quorum_is_addressed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            left, right = self.pair(root)
            left_json = root / "left.json"
            right_json = root / "right.json"
            left_json.write_text(registry_model.registry_json(left), encoding="utf-8")
            right_json.write_text(registry_model.registry_json(right), encoding="utf-8")
            normal = runtime_model.run_runtime((left_json, right_json), peer_ids=("left", "right"), quorum=2, runtime_id="same-id")
            relaxed = runtime_model.run_runtime((left_json, right_json), peer_ids=("left", "right"), quorum=1, runtime_id="same-id")
            self.assertNotEqual(normal.consensus.content_address, relaxed.consensus.content_address)
            self.assertNotEqual(normal.content_address, relaxed.content_address)
            self.assertEqual(runtime_model.runtime_from_mapping(normal.to_dict()).to_dict(), normal.to_dict())

    def test_cli_federation_flow_and_schema_routes_are_available(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            left, right = self.pair(root)
            left_dir = self.persist_registry(left, root / "left-registry")
            right_dir = self.persist_registry(right, root / "right-registry")
            destination = root / "runtime"
            output = root / "runtime.json"
            command = "registry-federation-consensus-gate-certificate-observatory-archive-registry-federation"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main([command, "--input", str(left_dir), "--input", str(right_dir), "--peer-id", "left", "--peer-id", "right", "--destination", str(destination), "--format", "json", "--output", str(output)]), 0)
            federation_path = destination / runtime_model.FEDERATION_NAME
            query_output = root / "query.json"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main([command + "-query", "--input", str(federation_path), "--resource", "observations", "--format", "json", "--output", str(query_output)]), 0)
                self.assertEqual(main([command + "-query-audit", "--input", str(query_output), "--format", "json", "--output", str(root / "query-audit.json")]), 0)
            self.assertTrue(json.loads((root / "query-audit.json").read_text(encoding="utf-8"))["accepted"])
            with contextlib.redirect_stdout(io.StringIO()) as captured:
                self.assertEqual(main([command + "-diff-query-audit-schema"]), 0)
            self.assertIsInstance(json.loads(captured.getvalue()), dict)
            parser = build_parser()
            choices = parser._subparsers._group_actions[0].choices
            self.assertIn(command + "-diff-query-audit", choices)

    def test_http_federation_flow_supports_schemas_query_diff_and_report(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            left, right = self.pair(root)
            left_dir = self.persist_registry(left, root / "left-registry")
            right_dir = self.persist_registry(right, root / "right-registry")
            left_fed = self.persist_federation(federation_model.build_federation((left,), peer_ids=("left",), federation_id="left-http"), root / "left.json")
            right_fed = self.persist_federation(federation_model.build_federation((right,), peer_ids=("right",), federation_id="right-http"), root / "right.json")
            server = create_server("127.0.0.1", 0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = f"http://127.0.0.1:{server.server_port}/v1/registry/federation/consensus/gate/certificate/observatory/archive/registry/federation"
                for suffix in ("/schema", "/audit/schema", "/query/result-schema", "/query-audit/schema", "/diff/schema", "/diff/query-audit/schema", "/consensus/schema", "/report/schema", "/runtime/schema"):
                    with urlopen(base + suffix, timeout=20) as response:
                        self.assertEqual(response.status, 200)
                        self.assertIsInstance(json.loads(response.read()), dict)
                request = urlencode((("input", str(left_dir)), ("input", str(right_dir)), ("peer_id", "left"), ("peer_id", "right"), ("quorum", "2"), ("format", "json")))
                with urlopen(base + "?" + request, timeout=30) as response:
                    runtime_payload = json.loads(response.read())
                    self.assertTrue(runtime_payload["accepted"])
                    federation_path = root / "http-federation.json"
                    federation_path.write_text(federation_model.federation_json(federation_model.federation_from_mapping(runtime_payload["federation"])), encoding="utf-8")
                query_request = urlencode((("input", str(federation_path)), ("resource", "observations"), ("limit", "1"), ("format", "json")))
                with urlopen(base + "/query?" + query_request, timeout=30) as response:
                    query_payload = json.loads(response.read())
                    self.assertEqual(query_payload["returned_count"], 1)
                diff_request = urlencode((("left", str(left_fed)), ("right", str(right_fed)), ("format", "json")))
                with urlopen(base + "/diff?" + diff_request, timeout=30) as response:
                    self.assertGreaterEqual(json.loads(response.read())["item_count"], 1)
                report_request = urlencode((("input", str(federation_path)), ("format", "json")))
                with urlopen(base + "/report?" + report_request, timeout=30) as response:
                    self.assertTrue(json.loads(response.read())["accepted"])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_schemas_capabilities_and_all_public_outputs_are_clean(self):
        schemas = (federation_model.peer_schema(), federation_model.observation_schema(), federation_model.federation_schema(), federation_audit_model.check_schema(), federation_audit_model.audit_schema(), query_model.query_schema(), query_model.row_schema(), query_model.result_schema(), query_audit_model.check_schema(), query_audit_model.audit_schema(), diff_model.item_schema(), diff_model.diff_schema(), diff_audit_model.check_schema(), diff_audit_model.audit_schema(), diff_query_model.query_schema(), diff_query_model.row_schema(), diff_query_model.result_schema(), diff_query_audit_model.check_schema(), diff_query_audit_model.audit_schema(), consensus_model.candidate_schema(), consensus_model.decision_schema(), consensus_model.consensus_schema(), consensus_audit_model.check_schema(), consensus_audit_model.audit_schema(), report_model.alert_schema(), report_model.report_schema(), report_audit_model.check_schema(), report_audit_model.audit_schema(), runtime_model.manifest_schema(), runtime_model.runtime_schema(), runtime_audit_model.check_schema(), runtime_audit_model.audit_schema())
        for schema in schemas:
            self.assert_closed(schema)
        value = self.federation(Path(tempfile.mkdtemp(prefix="glio-noncode-public-")))
        consensus = consensus_model.build_consensus(value)
        report = report_model.build_report(value, consensus=consensus)
        runtime = runtime_model.build_runtime(value, consensus=consensus, report=report)
        outputs = (value, federation_audit_model.audit_federation(value), query_model.query_federation(value), diff_model.build_diff(value, value), consensus, report, runtime, runtime_audit_model.audit_runtime(runtime))
        for item in outputs:
            self.assert_public(item)


if __name__ == "__main__":
    unittest.main()
