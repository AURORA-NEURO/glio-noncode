"""Deep contract tests for reconciliation decision closure and transitions."""

# ruff: noqa: E501, I001

from __future__ import annotations

import json
import tempfile
import threading
import unittest
from urllib.parse import urlencode
from urllib.request import urlopen
from pathlib import Path

from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive as archive_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry as registry_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation as federation_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_consensus as consensus_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_resolution as resolution_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_reconciliation_decision_ledger as ledger_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_reconciliation_decision_ledger_audit as ledger_audit_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_reconciliation_decision_ledger_diff as diff_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_reconciliation_decision_ledger_diff_audit as diff_audit_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_reconciliation_decision_ledger_diff_query as diff_query_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_reconciliation_decision_ledger_diff_query_audit as diff_query_audit_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_reconciliation_decision_ledger_query as query_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_reconciliation_decision_ledger_query_audit as query_audit_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_reconciliation_decision_ledger_runtime as runtime_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_reconciliation_decision_ledger_runtime_audit as runtime_audit_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_reconciliation_plan as plan_model
from glio_noncode.errors import ValidationError
from glio_noncode.api import create_server
from glio_noncode.cli import main
from tests import test_registry_federation_consensus_gate_certificate_observatory_archive as source_archive_tests


class DecisionLedgerFixture(unittest.TestCase):
    """Create verified plan inputs through the existing package boundary."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.source_fixture = source_archive_tests.CertificateObservatoryArchiveTests("runTest")
        cls.source_fixture.setUp()
        cls.fixture_root = Path(tempfile.mkdtemp(prefix="glio-noncode-decision-ledger-fixture-"))
        cls.fixture_package = cls.source_fixture._package(cls.fixture_root / "package", package_id="decision-ledger-package")

    @classmethod
    def tearDownClass(cls) -> None:
        import shutil

        shutil.rmtree(cls.fixture_root, ignore_errors=True)
        cls.source_fixture.tearDown()

    def _plan(self, root: Path, *, divergent: bool = False, missing: bool = False, quorum: int = 2) -> plan_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlan:
        package = self.fixture_package
        primary_archives = tuple(archive_model.build_archive(package, archive_id=archive_id) for archive_id in ("shared-a", "shared-b"))
        replica_archive_ids = ("shared-a",) if missing else ("shared-a", "shared-b")
        replica_archives = tuple(archive_model.build_archive(package, archive_id=("divergent-" + archive_id if divergent else archive_id)) for archive_id in replica_archive_ids)
        entry_ids = ("entry-a", "entry-b")
        primary = registry_model.build_registry_from_archives(primary_archives, entry_ids=entry_ids, registry_id="decision-ledger-primary")
        replica = registry_model.build_registry_from_archives(replica_archives, entry_ids=entry_ids[: len(replica_archives)], registry_id="decision-ledger-replica")
        federation = federation_model.build_federation((primary, replica), peer_ids=("primary", "replica"), federation_id="decision-ledger-federation")
        consensus = consensus_model.build_consensus(federation, consensus_id="decision-ledger-consensus", quorum=quorum)
        resolution = resolution_model.build_resolution(federation, consensus=consensus)
        return plan_model.build_plan(federation, resolution, consensus=consensus, plan_id="decision-ledger-plan")

    def _planned_plan(self, root: Path) -> plan_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlan:
        package = self.fixture_package
        archives = tuple(archive_model.build_archive(package, archive_id=archive_id) for archive_id in ("shared-a", "shared-b"))
        entry_ids = ("entry-a", "entry-b")
        primary = registry_model.build_registry_from_archives(archives, entry_ids=entry_ids, registry_id="decision-ledger-primary")
        replica = registry_model.build_registry_from_archives(archives, entry_ids=entry_ids, registry_id="decision-ledger-replica")
        partial = registry_model.build_registry_from_archives((archives[0],), entry_ids=("entry-a",), registry_id="decision-ledger-partial")
        federation = federation_model.build_federation((primary, replica, partial), peer_ids=("primary", "replica", "partial"), federation_id="decision-ledger-federation")
        consensus = consensus_model.build_consensus(federation, consensus_id="decision-ledger-consensus", quorum=2)
        resolution = resolution_model.build_resolution(federation, consensus=consensus)
        return plan_model.build_plan(federation, resolution, consensus=consensus, plan_id="decision-ledger-plan")

    def _assert_public(self, value: object) -> None:
        forbidden = {"agent", "agent_id", "agent_name", "assistant", "assistant_id", "author", "language", "model", "model_id", "programming_language"}

        def walk(node: object) -> None:
            if isinstance(node, dict):
                for key, child in node.items():
                    self.assertNotIn(str(key).casefold(), forbidden)
                    walk(child)
            elif isinstance(node, (tuple, list)):
                for child in node:
                    walk(child)

        walk(value)

    def test_clean_plan_defaults_to_complete_noop_closure(self):
        with tempfile.TemporaryDirectory() as temporary:
            plan = self._plan(Path(temporary))
            ledger = ledger_model.build_ledger(plan, ledger_id="clean-ledger")
            self.assertEqual((plan.operation_count, ledger.operation_count, ledger.decision_count), (4, 4, 4))
            self.assertEqual((ledger.not_required_count, ledger.pending_count, ledger.approved_count), (4, 0, 0))
            self.assertEqual((ledger.state, ledger.accepted, ledger.release_ready), ("ready", True, True))
            self.assertEqual(ledger_model.ledger_from_mapping(ledger.to_dict()).content_address, ledger.content_address)
            self.assertEqual(json.loads(ledger_model.ledger_json(ledger))["ledger_id"], "clean-ledger")
            self._assert_public(ledger.to_dict())

    def test_default_actionable_rows_are_pending_until_explicitly_decided(self):
        with tempfile.TemporaryDirectory() as temporary:
            plan = self._plan(Path(temporary), divergent=True, quorum=1)
            self.assertTrue(any(item.action != "no-op" for item in plan.operations))
            ledger = ledger_model.build_ledger(plan, ledger_id="pending-ledger")
            self.assertGreater(ledger.pending_count, 0)
            self.assertFalse(ledger.accepted)
            self.assertFalse(ledger.release_ready)
            self.assertEqual(ledger.state, "review")
            self.assertTrue(all(item.disposition == "not-required" for item in ledger.decisions if item.action == "no-op"))
            self.assertTrue(all(item.disposition == "pending" for item in ledger.decisions if item.action != "no-op"))

    def test_approve_mapping_closes_planned_actions_without_claiming_release(self):
        with tempfile.TemporaryDirectory() as temporary:
            plan = self._planned_plan(Path(temporary))
            approvals = {item.content_address: "approve" for item in plan.operations if item.action != "no-op"}
            ledger = ledger_model.apply_decisions(plan, approvals, ledger_id="approved-ledger")
            self.assertGreater(ledger.approved_count, 0)
            self.assertEqual((ledger.pending_count, ledger.held_count, ledger.rejected_count, ledger.deferred_count), (0, 0, 0, 0))
            self.assertTrue(ledger.accepted)
            self.assertFalse(ledger.release_ready)
            self.assertEqual(ledger.state, "authorized")

    def test_dispositions_are_constrained_by_plan_action(self):
        with tempfile.TemporaryDirectory() as temporary:
            clean_plan = self._plan(Path(temporary) / "clean")
            noop = clean_plan.operations[0]
            with self.assertRaises(ValidationError):
                ledger_model.decision_for_operation(noop, "approve")
            divergent_plan = self._plan(Path(temporary) / "divergent", divergent=True, quorum=1)
            planned = next(item for item in divergent_plan.operations if item.action != "no-op")
            with self.assertRaises(ValidationError):
                ledger_model.decision_for_operation(planned, "hold")
            held = ledger_model.decision_for_operation(planned, "hold", note="review evidence before separate execution")
            self.assertEqual((held.disposition, held.status), ("hold", "held"))
            with self.assertRaises(ValidationError):
                ledger_model.build_ledger(divergent_plan, {planned.content_address: held.to_dict() | {"note": ""}})

    def test_ledger_audit_is_fixed_size_and_independent_of_operational_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            for name, plan in (("clean", self._plan(Path(temporary) / "clean")), ("pending", self._plan(Path(temporary) / "pending", divergent=True, quorum=1))):
                ledger = ledger_model.build_ledger(plan, ledger_id=f"{name}-ledger")
                audit = ledger_audit_model.audit_ledger(ledger)
                self.assertEqual((audit.check_count, audit.passed_count, audit.failed_count, audit.accepted), (16, 16, 0, True))
                self.assertEqual(tuple(item.check_id for item in audit.checks), ledger_audit_model.CHECK_IDS)
                self.assertEqual(ledger_audit_model.audit_from_mapping(audit.to_dict()).content_address, audit.content_address)
                self.assertIn("# Archive Registry Federation Reconciliation Decision Ledger Audit", ledger_audit_model.render_audit_markdown(audit))

    def test_query_partitions_and_pagination_are_deterministic(self):
        with tempfile.TemporaryDirectory() as temporary:
            ledger = ledger_model.build_ledger(self._plan(Path(temporary)), ledger_id="query-ledger")
            all_rows = query_model.query_ledger(ledger, resources=("summary", "decisions"), limit=100)
            self.assertEqual((all_rows.total_count, all_rows.matched_count, all_rows.returned_count, all_rows.truncated), (5, 5, 5, False))
            status_rows = query_model.query_ledger(ledger, resources=("not-required",), status="not-required", limit=2)
            self.assertEqual((status_rows.matched_count, status_rows.returned_count, status_rows.next_offset, status_rows.truncated), (4, 2, 2, True))
            repeat = query_model.query_ledger(ledger, resources=("not-required",), status="not-required", offset=2, limit=5)
            self.assertEqual((repeat.returned_count, repeat.next_offset, repeat.truncated), (2, 4, False))
            self.assertEqual(query_model.query_from_mapping(all_rows.to_dict()).content_address, all_rows.content_address)
            self.assertTrue(query_model.query_csv(all_rows).startswith("ordinal,resource,row_id"))
            self.assertIn("# Archive Registry Federation Reconciliation Decision Ledger Query", query_model.render_query_markdown(all_rows))

    def test_query_audit_accepts_empty_page_and_exact_filters(self):
        with tempfile.TemporaryDirectory() as temporary:
            ledger = ledger_model.build_ledger(self._plan(Path(temporary)), ledger_id="query-audit-ledger")
            result = query_model.query_ledger(ledger, resources=("decisions",), peer_id="missing-peer", limit=10)
            audit = query_audit_model.audit_query(result)
            self.assertEqual((result.returned_count, result.matched_count, audit.check_count, audit.passed_count, audit.accepted), (0, 0, 12, 12, True))
            self.assertEqual(query_audit_model.audit_from_mapping(audit.to_dict()).content_address, audit.content_address)

    def test_runtime_persists_all_members_and_replays_from_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan = self._plan(root)
            destination = root / "decision-runtime"
            runtime = runtime_model.run_runtime(plan, runtime_id="decision-runtime", ledger_id="runtime-ledger", resources=("summary", "decisions"), limit=100, destination=destination)
            self.assertTrue(destination.is_dir())
            self.assertEqual(tuple(sorted(item.name for item in destination.iterdir())), tuple(sorted(runtime_model.FILES)))
            self.assertEqual((runtime.accepted, runtime.ledger_accepted, runtime.release_ready, runtime.state), (True, True, True, "ready"))
            self.assertEqual(runtime_model.load_runtime(destination).content_address, runtime.content_address)
            self.assertEqual(runtime_audit_model.audit_runtime(runtime).passed_count, 13)
            self.assertEqual(runtime_audit_model.audit_runtime(runtime).check_count, 13)
            self.assertEqual(runtime_model.runtime_from_mapping(json.loads(runtime_model.runtime_json(runtime))).content_address, runtime.content_address)

    def test_runtime_preserves_pending_state_but_structural_audit_still_passes(self):
        with tempfile.TemporaryDirectory() as temporary:
            plan = self._plan(Path(temporary), divergent=True, quorum=1)
            runtime = runtime_model.build_runtime(plan, runtime_id="pending-runtime", ledger_id="pending-runtime-ledger", limit=100)
            self.assertEqual((runtime.state, runtime.release_ready, runtime.ledger_accepted, runtime.accepted), ("review", False, False, True))
            audit = runtime_audit_model.audit_runtime(runtime)
            self.assertEqual((audit.passed_count, audit.failed_count, audit.accepted), (13, 0, True))

    def test_runtime_accepts_a_persisted_plan_runtime_directory_as_input(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan = self._plan(root)
            plan_directory = root / "plan-runtime"
            plan_runtime = runtime_model.run_runtime(plan, runtime_id="source-runtime", destination=plan_directory, limit=100)
            second = runtime_model.run_runtime(plan_directory, runtime_id="replayed-runtime", ledger_id="replayed-ledger", limit=100)
            self.assertEqual(second.plan.content_address, plan_runtime.plan.content_address)
            self.assertEqual(second.ledger.plan_address, plan.content_address)

    def test_cli_and_http_surfaces_materialize_the_same_decision_runtime(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan = self._planned_plan(root)
            plan_path = root / "plan.json"
            plan_path.write_text(json.dumps(plan.to_dict(), sort_keys=True), encoding="utf-8")
            runtime_path = root / "runtime.json"
            audit_path = root / "audit.json"
            command = "registry-federation-consensus-gate-certificate-observatory-archive-registry-federation-reconciliation-decision-ledger"
            audit_command = command + "-audit"
            self.assertEqual(main([command, "--input", str(plan_path), "--ledger-id", "surface-ledger", "--limit", "100", "--format", "json", "--output", str(runtime_path)]), 0)
            self.assertEqual(main([audit_command, "--input", str(runtime_path), "--format", "json", "--output", str(audit_path)]), 0)
            self.assertTrue(json.loads(audit_path.read_text(encoding="utf-8"))["accepted"])
            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                prefix = "/v1/registry/federation/consensus/gate/certificate/observatory/archive/registry/federation/reconciliation-decision-ledger"
                query = urlencode({"input": str(plan_path), "format": "summary", "limit": "100"})
                with urlopen(f"http://127.0.0.1:{server.server_port}{prefix}?{query}", timeout=20) as response:
                    payload = json.loads(response.read())
                self.assertEqual(payload["ledger_id"], ledger_model.DEFAULT_LEDGER_ID)
                with urlopen(f"http://127.0.0.1:{server.server_port}{prefix}/schema", timeout=20) as response:
                    self.assertEqual(json.loads(response.read())["$schema"], "https://json-schema.org/draft/2020-12/schema")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_diff_classifies_pending_to_approved_transition_and_queries_changes(self):
        with tempfile.TemporaryDirectory() as temporary:
            plan = self._planned_plan(Path(temporary))
            pending = ledger_model.build_ledger(plan, ledger_id="pending-diff-ledger")
            approvals = {item.content_address: "approve" for item in plan.operations if item.action != "no-op"}
            approved = ledger_model.build_ledger(plan, approvals, ledger_id="approved-diff-ledger")
            diff = diff_model.build_diff(pending, approved, diff_id="decision-transition")
            self.assertGreater(diff.changed_count, 0)
            self.assertGreater(diff.unchanged_count, 0)
            self.assertEqual(diff_model.diff_from_mapping(diff.to_dict()).content_address, diff.content_address)
            audit = diff_audit_model.audit_diff(diff)
            self.assertEqual((audit.check_count, audit.passed_count, audit.failed_count, audit.accepted), (13, 13, 0, True))
            result = diff_query_model.query_diff(diff, resources=("changed",), change="changed", limit=100)
            self.assertEqual(result.returned_count, diff.changed_count)
            self.assertEqual(diff_query_model.query_from_mapping(result.to_dict()).content_address, result.content_address)
            query_audit = diff_query_audit_model.audit_query(result)
            self.assertEqual((query_audit.check_count, query_audit.passed_count, query_audit.failed_count, query_audit.accepted), (11, 11, 0, True))

    def test_diff_of_identical_ledger_is_all_unchanged(self):
        with tempfile.TemporaryDirectory() as temporary:
            ledger = ledger_model.build_ledger(self._plan(Path(temporary)), ledger_id="same-ledger")
            diff = diff_model.build_diff(ledger, ledger, diff_id="self-diff")
            self.assertEqual((diff.added_count, diff.removed_count, diff.changed_count), (0, 0, 0))
            self.assertEqual(diff.unchanged_count, ledger.operation_count)
            self.assertTrue(diff_audit_model.audit_diff(diff).accepted)

    def test_mapping_rejects_tampered_addresses_and_unknown_fields(self):
        with tempfile.TemporaryDirectory() as temporary:
            ledger = ledger_model.build_ledger(self._plan(Path(temporary)), ledger_id="tamper-ledger")
            altered = ledger.to_dict()
            altered["content_address"] = ledger_model.LEDGER_PREFIX + ":tampered"
            with self.assertRaises(ValidationError):
                ledger_model.ledger_from_mapping(altered)
            unknown = ledger.to_dict()
            unknown["private_note"] = "not-public"
            with self.assertRaises(ValidationError):
                ledger_model.ledger_from_mapping(unknown)
            operation = ledger.decisions[0].to_dict()
            operation["status"] = "approved"
            with self.assertRaises(ValidationError):
                ledger_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecision.from_mapping(operation)

    def test_schemas_capabilities_and_renderings_are_public(self):
        values = (ledger_model.ledger_schema(), ledger_model.decision_schema(), ledger_audit_model.audit_schema(), ledger_audit_model.check_schema(), query_model.query_schema(), query_model.row_schema(), query_model.result_schema(), query_audit_model.audit_schema(), query_audit_model.check_schema(), diff_model.diff_schema(), diff_model.item_schema(), diff_audit_model.audit_schema(), diff_audit_model.check_schema(), diff_query_model.query_schema(), diff_query_model.row_schema(), diff_query_model.result_schema(), diff_query_audit_model.audit_schema(), diff_query_audit_model.check_schema(), runtime_model.runtime_schema(), runtime_model.manifest_schema(), runtime_audit_model.audit_schema(), runtime_audit_model.check_schema())
        for schema in values:
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
            self._assert_public(schema)
        capabilities = (ledger_model.capabilities(), ledger_audit_model.capabilities(), query_model.capabilities(), query_audit_model.capabilities(), diff_model.capabilities(), diff_audit_model.capabilities(), diff_query_model.capabilities(), diff_query_audit_model.capabilities(), runtime_model.capabilities(), runtime_audit_model.capabilities())
        for value in capabilities:
            self.assertTrue(value["public"])
            self._assert_public(value)


if __name__ == "__main__":
    unittest.main()
