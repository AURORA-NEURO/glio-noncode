"""Deep contract tests for federated archive-registry resolution and plans.

The fixture uses the repository's downloaded observatory package shape.  The
test suite keeps source paths at the edge and verifies that the public runtime,
resolution, plan, query, CLI, HTTP, and schema surfaces contain only replayable
evidence.
"""

# ruff: noqa: E501, I001

from __future__ import annotations

import contextlib
import hashlib
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
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_consensus as consensus_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_reconciliation_plan as plan_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_reconciliation_plan_audit as plan_audit_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_reconciliation_plan_query as plan_query_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_reconciliation_plan_query_audit as plan_query_audit_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_reconciliation_runtime as runtime_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_reconciliation_runtime_audit as runtime_audit_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_resolution as resolution_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_resolution_audit as resolution_audit_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_resolution_query as resolution_query_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_resolution_query_audit as resolution_query_audit_model
from glio_noncode.api import create_server
from glio_noncode.cli import build_parser, main
from glio_noncode.errors import ValidationError
from glio_noncode.public_surface_audit import default_public_surface_inventory
from tests import test_registry_federation_consensus_gate_certificate_observatory_archive as source_archive_tests


class ArchiveRegistryFederationReconciliationContractTests(unittest.TestCase):
    """Exercise the complete evidence-preserving reconciliation boundary."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.source_fixture = source_archive_tests.CertificateObservatoryArchiveTests("runTest")
        cls.source_fixture.setUp()
        cls.fixture_root = Path(tempfile.mkdtemp(prefix="glio-noncode-reconciliation-fixture-"))
        cls.fixture_package = cls.source_fixture._package(cls.fixture_root / "package", package_id="downloaded-observatory-package")

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.fixture_root, ignore_errors=True)
        cls.source_fixture.tearDown()

    def package(self, root: Path, package_id: str = "downloaded-observatory-package"):
        if package_id == "downloaded-observatory-package":
            return self.fixture_package
        return self.source_fixture._package(root / "package", package_id=package_id)

    def registry(self, root: Path, *archive_ids: str, registry_id: str = "downloaded-registry"):
        archives = tuple(archive_model.build_archive(self.package(root / "archives"), archive_id=archive_id) for archive_id in archive_ids)
        return registry_model.build_registry_from_archives(archives, entry_ids=tuple("entry-" + value for value in archive_ids), registry_id=registry_id)

    def persist_registry(self, value, destination: Path) -> Path:
        registry_model.write_registry(value, destination)
        return destination

    def matching_federation(self, root: Path):
        left, right = self.matching_registries(root)
        return federation_model.build_federation((left, right), peer_ids=("alpha", "beta"), federation_id="downloaded-registry-federation")

    def matching_registries(self, root: Path):
        left = self.registry(root / "left", "shared-a", "shared-b", registry_id="left-registry")
        right = self.registry(root / "right", "shared-a", "shared-b", registry_id="right-registry")
        return left, right

    def missing_federation(self, root: Path):
        shared = self.registry(root / "shared", "shared", registry_id="shared-registry")
        extra = self.registry(root / "extra", "shared", "only-left", registry_id="extra-registry")
        return federation_model.build_federation((shared, extra), peer_ids=("alpha", "beta"), federation_id="missing-entry-federation")

    def divergent_federation(self, root: Path):
        # Build three distinct addressed archives, then give them one shared
        # entry identity so consensus sees three non-quorate candidates.
        entries = []
        for peer in ("alpha", "beta", "gamma"):
            archive = archive_model.build_archive(self.package(root / peer / "archives"), archive_id="same-entry-" + peer)
            entry = registry_model.entry_from_archive(archive, entry_id="shared-entry")
            entries.append(registry_model.build_registry((entry,), registry_id=peer + "-registry"))
        return federation_model.build_federation(tuple(entries), peer_ids=("alpha", "beta", "gamma"), federation_id="divergent-federation")

    def assert_public(self, value: object) -> None:
        raw = value.to_dict() if hasattr(value, "to_dict") else value
        encoded = json.dumps(raw, sort_keys=True, default=list).lower()
        for forbidden in ("local_path", "generated_by", "agent", "assistant", "language", "private_key", "secret", "token"):
            self.assertNotIn(forbidden, encoded)

    def assert_closed(self, schema: dict[str, object]) -> None:
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(set(schema["required"]), set(schema["properties"]))

    def test_matching_resolution_is_ready_and_addressed(self):
        with tempfile.TemporaryDirectory() as temporary:
            federation = self.matching_federation(Path(temporary))
            consensus = consensus_model.build_consensus(federation, quorum=2)
            value = resolution_model.build_resolution(federation, consensus=consensus, resolution_id="matching-resolution")
            self.assertEqual((value.state, value.accepted, value.release_ready, value.resolved_count, value.review_count, value.blocked_count), ("ready", True, True, 2, 0, 0))
            self.assertTrue(all(item.action == "retain-consensus" and item.selected_archive_address for item in value.items))
            self.assertEqual(resolution_model.resolution_from_mapping(value.to_dict()).to_dict(), value.to_dict())
            self.assertEqual(resolution_model.address_resolution(value), value.content_address)
            self.assertTrue(resolution_audit_model.audit_resolution(value).accepted)
            self.assert_public(value)

    def test_missing_evidence_becomes_blocked_request_without_selection(self):
        with tempfile.TemporaryDirectory() as temporary:
            federation = self.missing_federation(Path(temporary))
            consensus = consensus_model.build_consensus(federation, quorum=2)
            value = resolution_model.build_resolution(federation, consensus=consensus)
            item = value.item("entry-only-left")
            self.assertEqual((item.state, item.action, item.rationale), ("blocked", "request-missing", "quorum-unmet-missing"))
            self.assertEqual(item.selected_archive_address, "")
            self.assertEqual(item.missing_peer_ids, ("beta",))
            self.assertFalse(value.release_ready)
            self.assertTrue(resolution_audit_model.audit_resolution(value).accepted)

    def test_three_way_divergence_is_review_not_silent_winner(self):
        with tempfile.TemporaryDirectory() as temporary:
            federation = self.divergent_federation(Path(temporary))
            value = resolution_model.build_resolution(federation, consensus=consensus_model.build_consensus(federation, quorum=2))
            item = value.item("shared-entry")
            self.assertEqual((value.state, value.review_count, value.blocked_count), ("review", 1, 0))
            self.assertEqual((item.state, item.action, item.rationale), ("review", "review-divergence", "quorum-unmet-divergence"))
            self.assertEqual(len(item.candidate_addresses), 3)
            self.assertEqual(item.supporting_peer_ids, ())
            self.assertEqual(item.dissenting_peer_ids, ("alpha", "beta", "gamma"))
            self.assertTrue(resolution_audit_model.audit_resolution(value).accepted)

    def test_plan_expands_every_entry_peer_pair_and_preserves_actions(self):
        with tempfile.TemporaryDirectory() as temporary:
            federation = self.matching_federation(Path(temporary))
            consensus = consensus_model.build_consensus(federation, quorum=2)
            resolution = resolution_model.build_resolution(federation, consensus=consensus)
            plan = plan_model.build_plan(federation, resolution, consensus=consensus)
            self.assertEqual(plan.operation_count, plan.peer_count * plan.entry_count)
            self.assertEqual((plan.state, plan.accepted, plan.release_ready, plan.noop_count), ("ready", True, True, 4))
            self.assertTrue(all(item.action == "no-op" and item.status == "no-op" for item in plan.operations))
            self.assertEqual(plan_model.plan_from_mapping(plan.to_dict()).to_dict(), plan.to_dict())
            self.assertTrue(plan_audit_model.audit_plan(plan).accepted)
            self.assert_public(plan)

    def test_missing_plan_has_high_requests_and_critical_blocked_rows(self):
        with tempfile.TemporaryDirectory() as temporary:
            federation = self.missing_federation(Path(temporary))
            consensus = consensus_model.build_consensus(federation, quorum=2)
            resolution = resolution_model.build_resolution(federation, consensus=consensus)
            plan = plan_model.build_plan(federation, resolution, consensus=consensus)
            rows = tuple(item for item in plan.operations if item.entry_id == "entry-only-left")
            self.assertEqual(len(rows), 2)
            self.assertEqual({item.action for item in rows}, {"request-missing", "manual-review"})
            self.assertEqual({item.status for item in rows}, {"blocked"})
            self.assertEqual({item.priority for item in rows}, {"critical"})
            self.assertTrue(all(item.requires_confirmation for item in rows))
            self.assertFalse(plan.release_ready)
            self.assertTrue(plan_audit_model.audit_plan(plan).accepted)

    def test_divergent_plan_requires_manual_review_for_each_peer(self):
        with tempfile.TemporaryDirectory() as temporary:
            federation = self.divergent_federation(Path(temporary))
            consensus = consensus_model.build_consensus(federation, quorum=2)
            resolution = resolution_model.build_resolution(federation, consensus=consensus)
            plan = plan_model.build_plan(federation, resolution, consensus=consensus)
            self.assertEqual((plan.state, plan.accepted, plan.release_ready), ("review", True, False))
            self.assertEqual((plan.review_count, plan.blocked_count), (3, 0))
            self.assertTrue(all(item.action == "manual-review" and item.status == "review" for item in plan.operations))

    def test_resolution_query_filters_and_query_audit_replay(self):
        with tempfile.TemporaryDirectory() as temporary:
            federation = self.missing_federation(Path(temporary))
            resolution = resolution_model.build_resolution(federation, consensus=consensus_model.build_consensus(federation, quorum=2))
            result = resolution_query_model.query_resolution(resolution, resources=resolution_query_model.RESOURCES, limit=100)
            self.assertEqual((result.total_count, result.matched_count, result.returned_count), (9, 9, 9))
            self.assertTrue(resolution_query_audit_model.audit_query(result).accepted)
            blocked = resolution_query_model.query_resolution(resolution, resources=("blocked",), state="blocked", limit=10)
            self.assertEqual((blocked.matched_count, blocked.returned_count), (1, 1))
            self.assertEqual(blocked.rows[0].state, "blocked")
            self.assertEqual(resolution_query_model.query_from_mapping(result.to_dict()).to_dict(), result.to_dict())

    def test_plan_query_filters_pagination_and_audit_replay(self):
        with tempfile.TemporaryDirectory() as temporary:
            federation = self.missing_federation(Path(temporary))
            consensus = consensus_model.build_consensus(federation, quorum=2)
            resolution = resolution_model.build_resolution(federation, consensus=consensus)
            plan = plan_model.build_plan(federation, resolution, consensus=consensus)
            result = plan_query_model.query_plan(plan, resources=plan_query_model.RESOURCES, limit=100)
            self.assertEqual(result.total_count, 5)
            self.assertEqual(result.returned_count, 5)
            self.assertTrue(plan_query_audit_model.audit_query(result).accepted)
            page = plan_query_model.query_plan(plan, resources=("blocked",), status="blocked", offset=1, limit=1)
            self.assertEqual((page.matched_count, page.returned_count, page.next_offset, page.rows[0].ordinal), (2, 1, 2, 2))
            self.assertTrue(page.truncated)
            self.assertEqual(plan_query_model.query_from_mapping(result.to_dict()).to_dict(), result.to_dict())

    def test_query_tampering_is_rejected_by_address_and_ordinal_checks(self):
        with tempfile.TemporaryDirectory() as temporary:
            federation = self.matching_federation(Path(temporary))
            resolution = resolution_model.build_resolution(federation)
            query = resolution_query_model.query_resolution(resolution, limit=50)
            altered = json.loads(resolution_query_model.query_json(query))
            altered["rows"][0]["ordinal"] = 99
            with self.assertRaises(ValidationError):
                resolution_query_model.query_from_mapping(altered)
            federation = self.missing_federation(Path(temporary) / "missing")
            plan = plan_model.build_plan(federation, resolution_model.build_resolution(federation, consensus=consensus_model.build_consensus(federation, quorum=2)))
            plan_query = plan_query_model.query_plan(plan, limit=50)
            altered_plan_query = json.loads(plan_query_model.query_json(plan_query))
            altered_plan_query["content_address"] = "wrong:query"
            with self.assertRaises(ValidationError):
                plan_query_model.query_from_mapping(altered_plan_query)

    def test_runtime_persists_exact_nine_files_and_replays_from_disk(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            left, right = self.matching_registries(root)
            # The federation helper retains typed registries; rebuild source
            # directories from those values so the runtime tests actual files.
            left_dir = self.persist_registry(left, root / "left-registry")
            right_dir = self.persist_registry(right, root / "right-registry")
            destination = root / "runtime"
            value = runtime_model.run_runtime((left_dir, right_dir), peer_ids=("alpha", "beta"), quorum=2, runtime_id="persisted-runtime", destination=destination)
            self.assertTrue(value.accepted)
            self.assertEqual(tuple(sorted(item.name for item in destination.iterdir())), tuple(sorted(runtime_model.FILES)))
            replay = runtime_model.load_runtime(destination)
            self.assertEqual(replay.to_dict(), value.to_dict())
            self.assertEqual(runtime_model.verify_runtime_directory(destination).content_address, value.content_address)
            self.assertTrue(runtime_audit_model.audit_runtime(replay).accepted)

    def test_runtime_accepts_public_registry_json_and_quorum_changes_address(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            left, right = self.matching_registries(root)
            left_json = root / "left.json"
            right_json = root / "right.json"
            left_json.write_text(registry_model.registry_json(left), encoding="utf-8")
            right_json.write_text(registry_model.registry_json(right), encoding="utf-8")
            strict = runtime_model.run_runtime((left_json, right_json), peer_ids=("alpha", "beta"), quorum=2, runtime_id="same-runtime")
            relaxed = runtime_model.run_runtime((left_json, right_json), peer_ids=("alpha", "beta"), quorum=1, runtime_id="same-runtime")
            self.assertNotEqual(strict.consensus.content_address, relaxed.consensus.content_address)
            self.assertNotEqual(strict.content_address, relaxed.content_address)
            self.assertEqual(runtime_model.runtime_from_mapping(strict.to_dict()).to_dict(), strict.to_dict())

    def test_runtime_rejects_extra_and_noncanonical_members(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            destination = root / "runtime"
            left, right = self.matching_registries(root)
            runtime_model.run_runtime((self.persist_registry(left, root / "alpha"), self.persist_registry(right, root / "beta")), peer_ids=("alpha", "beta"), quorum=2, destination=destination)
            (destination / "extra.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(ValidationError):
                runtime_model.load_runtime(destination)
            (destination / "extra.json").unlink()
            raw = (destination / runtime_model.FEDERATION_NAME).read_bytes()
            (destination / runtime_model.FEDERATION_NAME).write_bytes(raw + b" ")
            with self.assertRaises(ValidationError):
                runtime_model.load_runtime(destination)

    def test_noop_runtime_does_not_mutate_source_registry_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            left, right = self.matching_registries(root)
            source_dirs = (self.persist_registry(left, root / "alpha"), self.persist_registry(right, root / "beta"))
            before = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for directory in source_dirs for path in directory.iterdir()}
            runtime_model.run_runtime(source_dirs, peer_ids=("alpha", "beta"), quorum=2, runtime_id="nonmutating")
            after = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for directory in source_dirs for path in directory.iterdir()}
            self.assertEqual(before, after)

    def test_cli_builds_runtime_resolution_plan_queries_and_schemas(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            left, right = self.matching_registries(root)
            source_dirs = (self.persist_registry(left, root / "alpha"), self.persist_registry(right, root / "beta"))
            runtime_destination = root / "runtime"
            runtime_json = root / "runtime.json"
            runtime_command = "registry-federation-consensus-gate-certificate-observatory-archive-registry-federation-reconciliation-runtime"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main([runtime_command, "--input", str(source_dirs[0]), "--input", str(source_dirs[1]), "--peer-id", "alpha", "--peer-id", "beta", "--quorum", "2", "--destination", str(runtime_destination), "--format", "json", "--output", str(runtime_json)]), 0)
            resolution_json = root / "resolution.json"
            resolution_command = runtime_command[:-len("-reconciliation-runtime")] + "-resolution"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main([resolution_command, "--input", str(runtime_destination / runtime_model.FEDERATION_NAME), "--quorum", "2", "--format", "json", "--output", str(resolution_json)]), 0)
            resolution_query_json = root / "resolution-query.json"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main([resolution_command + "-query", "--input", str(resolution_json), "--resource", "resolved", "--format", "json", "--output", str(resolution_query_json)]), 0)
                self.assertEqual(main([resolution_command + "-query-audit", "--input", str(resolution_query_json), "--format", "json", "--output", str(root / "resolution-query-audit.json")]), 0)
                self.assertEqual(main([runtime_command[:-len("-reconciliation-runtime")] + "-reconciliation-plan", "--input", str(runtime_json), "--format", "json", "--output", str(root / "plan.json")]), 0)
            self.assertTrue(json.loads((root / "resolution-query-audit.json").read_text(encoding="utf-8"))["accepted"])
            parser = build_parser()
            choices = parser._subparsers._group_actions[0].choices
            self.assertIn(runtime_command + "-audit", choices)
            with contextlib.redirect_stdout(io.StringIO()) as captured:
                self.assertEqual(main([resolution_command + "-schema"]), 0)
            self.assertFalse("local_path" in captured.getvalue())

    def test_http_routes_build_runtime_resolution_plan_and_expose_schemas(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            left, right = self.matching_registries(root)
            source_dirs = (self.persist_registry(left, root / "alpha"), self.persist_registry(right, root / "beta"))
            server = create_server("127.0.0.1", 0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = f"http://127.0.0.1:{server.server_port}/v1/registry/federation/consensus/gate/certificate/observatory/archive/registry/federation"
                for suffix in ("/resolution/schema", "/resolution/query/result-schema", "/reconciliation-plan/schema", "/reconciliation-runtime/manifest-schema", "/reconciliation-runtime/audit/schema"):
                    with urlopen(base + suffix, timeout=20) as response:
                        self.assertEqual(response.status, 200)
                        self.assertIsInstance(json.loads(response.read()), dict)
                request = urlencode((
                    ("input", str(source_dirs[0])),
                    ("input", str(source_dirs[1])),
                    ("peer_id", "alpha"),
                    ("peer_id", "beta"),
                    ("quorum", "2"),
                    ("format", "json"),
                ))
                with urlopen(base + "/reconciliation-runtime?" + request, timeout=30) as response:
                    runtime_payload = json.loads(response.read())
                    self.assertTrue(runtime_payload["accepted"])
                    federation_json = root / "federation.json"
                    federation_json.write_text(federation_model.federation_json(federation_model.federation_from_mapping(runtime_payload["federation"])), encoding="utf-8")
                resolution_request = urlencode((("input", str(federation_json)), ("quorum", "2"), ("format", "json")))
                with urlopen(base + "/resolution?" + resolution_request, timeout=30) as response:
                    resolution_payload = json.loads(response.read())
                    self.assertEqual(resolution_payload["state"], "ready")
                # The plan route accepts a runtime JSON handoff; materialize it
                # from the response so the HTTP test is independent of CLI.
                runtime_json = root / "runtime.json"
                runtime_json.write_text(json.dumps(runtime_payload), encoding="utf-8")
                with urlopen(base + "/reconciliation-plan?" + urlencode((("input", str(runtime_json)), ("format", "json"))), timeout=30) as response:
                    self.assertEqual(json.loads(response.read())["state"], "ready")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_all_new_schemas_are_closed_and_public_inventory_is_extended(self):
        schemas = (
            resolution_model.item_schema(),
            resolution_model.resolution_schema(),
            resolution_audit_model.check_schema(),
            resolution_audit_model.audit_schema(),
            resolution_query_model.query_schema(),
            resolution_query_model.row_schema(),
            resolution_query_model.result_schema(),
            resolution_query_audit_model.check_schema(),
            resolution_query_audit_model.audit_schema(),
            plan_model.operation_schema(),
            plan_model.plan_schema(),
            plan_audit_model.check_schema(),
            plan_audit_model.audit_schema(),
            plan_query_model.query_schema(),
            plan_query_model.row_schema(),
            plan_query_model.result_schema(),
            plan_query_audit_model.check_schema(),
            plan_query_audit_model.audit_schema(),
            runtime_model.manifest_schema(),
            runtime_model.runtime_schema(),
            runtime_audit_model.check_schema(),
            runtime_audit_model.audit_schema(),
        )
        for schema in schemas:
            self.assert_closed(schema)
        inventory = default_public_surface_inventory()
        self.assertIn("archive-registry-federation-resolution-schema", inventory)
        self.assertIn("archive-registry-federation-reconciliation-plan-query-audit-schema", inventory)
        self.assertIn("archive-registry-federation-reconciliation-runtime-schema", inventory)

    def test_public_summaries_and_audits_contain_no_private_fields(self):
        with tempfile.TemporaryDirectory() as temporary:
            federation = self.matching_federation(Path(temporary))
            consensus = consensus_model.build_consensus(federation, quorum=2)
            resolution = resolution_model.build_resolution(federation, consensus=consensus)
            plan = plan_model.build_plan(federation, resolution, consensus=consensus)
            runtime = runtime_model.build_runtime(federation, consensus=consensus, resolution=resolution, plan=plan)
            values = (
                resolution,
                resolution_audit_model.audit_resolution(resolution),
                resolution_query_model.query_resolution(resolution),
                resolution_query_audit_model.audit_query(resolution_query_model.query_resolution(resolution)),
                plan,
                plan_audit_model.audit_plan(plan),
                plan_query_model.query_plan(plan),
                plan_query_audit_model.audit_query(plan_query_model.query_plan(plan)),
                runtime,
                runtime_audit_model.audit_runtime(runtime),
            )
            for value in values:
                self.assert_public(value)

    def test_exports_are_stable_and_retain_the_same_public_addresses(self):
        with tempfile.TemporaryDirectory() as temporary:
            federation = self.matching_federation(Path(temporary))
            consensus = consensus_model.build_consensus(federation, quorum=2)
            resolution = resolution_model.build_resolution(federation, consensus=consensus)
            plan = plan_model.build_plan(federation, resolution, consensus=consensus)
            self.assertIsInstance(json.loads(resolution_model.resolution_json(resolution)), dict)
            self.assertIn("# Archive Registry Federation Resolution", resolution_model.render_resolution_markdown(resolution))
            self.assertIn("content_address", resolution_model.resolution_csv(resolution).splitlines()[0])
            self.assertIn("# Archive Registry Federation Reconciliation Plan", plan_model.render_plan_markdown(plan))
            self.assertIn("content_address", plan_model.plan_csv(plan).splitlines()[0])
            self.assertEqual(resolution_model.resolution_from_mapping(json.loads(resolution_model.resolution_json(resolution))).content_address, resolution.content_address)
            self.assertEqual(plan_model.plan_from_mapping(json.loads(plan_model.plan_json(plan))).content_address, plan.content_address)

    def test_resolution_and_plan_identifiers_and_quorum_change_addresses(self):
        with tempfile.TemporaryDirectory() as temporary:
            federation = self.matching_federation(Path(temporary))
            strict_consensus = consensus_model.build_consensus(federation, quorum=2)
            relaxed_consensus = consensus_model.build_consensus(federation, quorum=1)
            strict = resolution_model.build_resolution(federation, consensus=strict_consensus, resolution_id="strict")
            relaxed = resolution_model.build_resolution(federation, consensus=relaxed_consensus, resolution_id="strict")
            self.assertNotEqual(strict.content_address, relaxed.content_address)
            strict_plan = plan_model.build_plan(federation, strict, consensus=strict_consensus, plan_id="plan")
            relaxed_plan = plan_model.build_plan(federation, relaxed, consensus=relaxed_consensus, plan_id="plan")
            self.assertNotEqual(strict_plan.content_address, relaxed_plan.content_address)
            renamed = resolution_model.build_resolution(federation, consensus=strict_consensus, resolution_id="renamed")
            self.assertNotEqual(strict.content_address, renamed.content_address)

    def test_runtime_overwrite_is_explicit_and_atomic(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            left, right = self.matching_registries(root)
            sources = (self.persist_registry(left, root / "left"), self.persist_registry(right, root / "right"))
            destination = root / "runtime"
            first = runtime_model.run_runtime(sources, peer_ids=("alpha", "beta"), quorum=2, runtime_id="first", destination=destination)
            with self.assertRaises(ValidationError):
                runtime_model.run_runtime(sources, peer_ids=("alpha", "beta"), quorum=2, runtime_id="second", destination=destination)
            second = runtime_model.run_runtime(sources, peer_ids=("alpha", "beta"), quorum=2, runtime_id="second", destination=destination, overwrite=True)
            self.assertNotEqual(first.content_address, second.content_address)
            self.assertEqual(runtime_model.load_runtime(destination).content_address, second.content_address)

    def test_manifest_receipts_cover_every_non_manifest_runtime_member(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            left, right = self.matching_registries(root)
            runtime = runtime_model.run_runtime((self.persist_registry(left, root / "left"), self.persist_registry(right, root / "right")), peer_ids=("alpha", "beta"), quorum=2)
            manifest = runtime_model.manifest_document(runtime)
            self.assertEqual(tuple(manifest["files"]), runtime_model.FILES)
            self.assertEqual(len(manifest["artifacts"]), len(runtime_model.FILES) - 1)
            self.assertTrue(all(item["name"] in runtime_model.FILES[1:] and item["size"] > 0 and ":" in item["hash"] for item in manifest["artifacts"]))
            self.assertEqual(runtime_model.runtime_from_mapping(json.loads(runtime_model.runtime_json(runtime))).content_address, runtime.content_address)

    def test_empty_sources_and_malformed_public_inputs_fail_closed(self):
        with self.assertRaises(ValidationError):
            runtime_model.run_runtime(())
        with self.assertRaises(ValidationError):
            runtime_model.load_registry_input({"unexpected": "field"})
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "invalid.json"
            source.write_text("[]", encoding="utf-8")
            with self.assertRaises(ValidationError):
                runtime_model.load_registry_input(source)

    def test_blocked_runtime_is_auditable_but_not_release_ready(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            left = self.persist_registry(self.registry(root / "left", "shared", registry_id="left-registry"), root / "left-registry")
            right = self.persist_registry(self.registry(root / "right", "shared", "only-left", registry_id="right-registry"), root / "right-registry")
            runtime = runtime_model.run_runtime((left, right), peer_ids=("alpha", "beta"), quorum=2, runtime_id="blocked")
            self.assertEqual((runtime.state, runtime.accepted, runtime.release_ready), ("blocked", True, False))
            self.assertTrue(runtime_audit_model.audit_runtime(runtime).accepted)
            self.assertEqual(runtime.resolution.blocked_count, 1)
            self.assertGreater(runtime.plan.blocked_count, 0)

    def test_query_text_and_peer_filters_select_only_evidence_rows(self):
        with tempfile.TemporaryDirectory() as temporary:
            federation = self.missing_federation(Path(temporary))
            consensus = consensus_model.build_consensus(federation, quorum=2)
            resolution = resolution_model.build_resolution(federation, consensus=consensus)
            plan = plan_model.build_plan(federation, resolution, consensus=consensus)
            resolution_page = resolution_query_model.query_resolution(resolution, resources=("missing",), peer_id="beta", text="only-left", limit=10)
            self.assertEqual(resolution_page.returned_count, 1)
            self.assertEqual(resolution_page.rows[0].entry_id, "entry-only-left")
            plan_page = plan_query_model.query_plan(plan, resources=("manual-review",), peer_id="alpha", entry_id="entry-only-left", limit=10)
            self.assertEqual(plan_page.returned_count, 1)
            self.assertEqual(plan_page.rows[0].action, "manual-review")
            self.assertTrue(resolution_query_audit_model.audit_query(resolution_page).accepted)
            self.assertTrue(plan_query_audit_model.audit_query(plan_page).accepted)


if __name__ == "__main__":
    unittest.main()
