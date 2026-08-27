"""Deep regression coverage for catalog assurance and release gates."""

# ruff: noqa: E501

from __future__ import annotations

import csv
import json
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlencode

from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog import (
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog,
    load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog,
    write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog,
)
from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance import (
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance,
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance_from_directory,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance_capabilities,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance_csv,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance_json,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance_query_capabilities,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance_query_json,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance_query_schema,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance_schema,
    query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance,
    render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance_markdown,
    render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance_query_markdown,
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance,
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance_query,
)
from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation import (
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation,
)
from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate import (
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate,
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate_from_directory,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate_capabilities,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate_csv,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate_json,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate_query_capabilities,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate_query_json,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate_query_schema,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate_schema,
    query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate,
    render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate_markdown,
    render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate_query_markdown,
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate,
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate_query,
)
from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime import (
    run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime,
)


class CatalogAssuranceGateTests(unittest.TestCase):
    """Exercise the independent assurance and release boundary."""

    @staticmethod
    def _store(
        store_id: str,
        *,
        state: str = "ready",
        release_ready: bool = True,
        accepted: bool = True,
        window_address: str = "window:one",
        ledger_address: str | None = None,
    ) -> SimpleNamespace:
        ledger = SimpleNamespace(
            window_address=window_address,
            content_address=ledger_address or f"ledger:{store_id}",
            head_address=f"entry:{store_id}",
            entry_count=1,
        )
        return SimpleNamespace(
            store_id=store_id,
            content_address=f"store:{store_id}",
            ledger_address=ledger.content_address,
            head_address=ledger.head_address,
            entry_count=1,
            state=state,
            release_ready=release_ready,
            accepted=accepted,
            append_only=True,
            operation_count=1,
            ledger=ledger,
        )

    def _catalog(self, *stores: SimpleNamespace, catalog_id: str = "catalog"):
        return build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
            stores,
            catalog_id=catalog_id,
        )

    def _ready(self):
        return self._catalog(self._store("alpha"), self._store("beta"))

    def _assurance(self, catalog=None, **kwargs):
        return build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance(
            catalog or self._ready(), **kwargs
        )

    def _gate(self, catalog=None, **kwargs):
        catalog = catalog or self._ready()
        runtime = run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime(
            catalog
        )
        federation = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation(
            catalog,
            **{
                key: value
                for key, value in kwargs.items()
                if key
                in {
                    "federation_id",
                    "selected_window_address",
                    "store_ids",
                    "require_same_window",
                    "require_unique_ledger",
                    "minimum_members",
                    "minimum_ready",
                }
            },
        )
        assurance = self._assurance(catalog)
        return build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate(
            catalog, runtime, federation, assurance, gate_id=kwargs.get("gate_id", "gate")
        )

    def test_ready_assurance_recomputes_all_catalog_relationships(self) -> None:
        assurance = self._assurance()
        self.assertEqual(assurance.state, "passed")
        self.assertTrue(assurance.accepted)
        self.assertTrue(assurance.release_ready)
        self.assertEqual(assurance.finding_count, 13)
        self.assertEqual(assurance.passed_count, 13)
        self.assertEqual(assurance.warning_count, 0)
        self.assertEqual(assurance.blocker_count, 0)
        self.assertTrue(
            verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance(
                assurance
            ).accepted
        )

    def test_assurance_finding_planes_and_counts_are_conserved(self) -> None:
        assurance = self._assurance()
        planes = {finding.plane for finding in assurance.findings}
        self.assertEqual(
            planes,
            {"catalog", "entries", "operations", "windows", "hydration", "readiness", "public"},
        )
        self.assertEqual(
            assurance.passed_count + assurance.warning_count + assurance.blocker_count,
            assurance.finding_count,
        )
        self.assertEqual([finding.ordinal for finding in assurance.findings], list(range(13)))
        self.assertEqual([finding.severity for finding in assurance.findings], ["pass"] * 13)

    def test_assurance_json_csv_markdown_are_deterministic(self) -> None:
        assurance = self._assurance()
        self.assertEqual(
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance_json(
                assurance
            ),
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance_json(
                assurance
            ),
        )
        document = json.loads(
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance_json(
                assurance
            )
        )
        self.assertEqual(document["content_address"], assurance.content_address)
        csv_value = module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance_csv(
            assurance
        )
        rows = list(csv.DictReader(csv_value.splitlines()))
        self.assertEqual(len(rows), assurance.finding_count)
        markdown = render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance_markdown(
            assurance
        )
        self.assertIn("Durable Review-Store Catalog Assurance", markdown)
        self.assertIn("public-boundary", markdown)

    def test_assurance_query_filters_receipts_and_exports(self) -> None:
        assurance = self._assurance()
        result = query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance(
            assurance, plane="readiness", passed=True, limit=2
        )
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["items"][0]["kind"], "release-readiness")
        self.assertTrue(
            verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance_query(
                result
            )
        )
        self.assertIn(
            "readiness",
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance_query_json(
                result
            ),
        )
        self.assertIn(
            "Catalog Assurance Query",
            render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance_query_markdown(
                result
            ),
        )

    def test_assurance_query_receipt_tampering_is_rejected(self) -> None:
        assurance = self._assurance()
        result = query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance(
            assurance, severity="pass"
        )
        result["total"] = 0
        with self.assertRaises(ValidationError):
            verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance_query(
                result
            )

    def test_assurance_schema_and_capabilities_are_identity_free(self) -> None:
        schema = module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance_schema()
        capabilities = module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance_capabilities()
        query_schema = module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance_query_schema()
        query_capabilities = module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance_query_capabilities()
        for value in (schema, capabilities, query_schema, query_capabilities):
            self.assertNotIn("agent", json.dumps(value).casefold())
            self.assertNotIn("language", json.dumps(value).casefold())
        self.assertTrue(capabilities["recomputes_catalog_links"])
        self.assertTrue(query_capabilities["addressed_receipts"])

    def test_assurance_from_directory_rehydrates_path_free_catalog(self) -> None:
        catalog = self._ready()
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "catalog"
            write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
                catalog, destination
            )
            assurance = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance_from_directory(
                destination
            )
            loaded = load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
                destination
            )
            self.assertEqual(assurance.catalog_address, loaded.content_address)
            self.assertNotIn(str(destination), json.dumps(assurance.to_dict()))

    def test_held_catalog_assurance_is_accepted_with_warning(self) -> None:
        assurance = self._assurance(
            self._catalog(self._store("held", state="held", release_ready=False))
        )
        self.assertEqual(assurance.state, "warning")
        self.assertTrue(assurance.accepted)
        self.assertFalse(assurance.release_ready)
        self.assertEqual(assurance.warning_count, 1)
        readiness = next(item for item in assurance.findings if item.kind == "release-readiness")
        self.assertFalse(readiness.passed)
        self.assertEqual(readiness.severity, "warning")

    def test_blocked_catalog_assurance_fails_closed(self) -> None:
        catalog = self._catalog(
            self._store("blocked", state="blocked", release_ready=False, accepted=False)
        )
        assurance = self._assurance(catalog)
        self.assertEqual(assurance.state, "blocked")
        self.assertFalse(assurance.accepted)
        self.assertFalse(assurance.release_ready)
        self.assertGreaterEqual(assurance.blocker_count, 1)
        self.assertEqual(
            next(item for item in assurance.findings if item.kind == "member-acceptance").severity,
            "blocker",
        )

    def test_assurance_hydration_mismatch_is_a_blocker(self) -> None:
        catalog = self._ready()
        wrong = self._store("alpha")
        wrong.content_address = "store:wrong"
        assurance = self._assurance(catalog, stores=(wrong, self._store("beta")))
        self.assertFalse(assurance.accepted)
        self.assertEqual(assurance.state, "blocked")
        self.assertFalse(
            next(item for item in assurance.findings if item.kind == "hydrated-members").passed
        )

    def test_assurance_rejects_duplicate_hydration_members(self) -> None:
        catalog = self._ready()
        assurance = self._assurance(
            catalog,
            stores=(self._store("alpha"), self._store("alpha"), self._store("beta")),
        )
        self.assertEqual(assurance.state, "blocked")
        self.assertFalse(assurance.accepted)
        self.assertFalse(
            next(item for item in assurance.findings if item.kind == "hydrated-members").passed
        )

    def test_assurance_acceptance_conservation_is_explicit(self) -> None:
        assurance = self._assurance()
        finding = next(
            item for item in assurance.findings if item.kind == "acceptance-conservation"
        )
        self.assertTrue(finding.passed)
        self.assertEqual(finding.expected, finding.observed)

    def test_assurance_invalid_filters_fail_closed(self) -> None:
        assurance = self._assurance()
        with self.assertRaises(ValidationError):
            query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance(
                assurance, plane="unknown"
            )
        with self.assertRaises(ValidationError):
            query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance(
                assurance, severity="unknown"
            )
        with self.assertRaises(ValidationError):
            query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance(
                assurance, offset=-1
            )

    def test_ready_gate_closes_all_four_evidence_planes(self) -> None:
        gate = self._gate()
        self.assertEqual(gate.state, "ready")
        self.assertTrue(gate.accepted)
        self.assertTrue(gate.release_ready)
        self.assertEqual(gate.member_count, 2)
        self.assertEqual(gate.ready_count, 2)
        self.assertEqual(gate.check_count, 14)
        self.assertEqual(gate.passed_count, 14)
        self.assertEqual(gate.warning_count, 0)
        self.assertEqual(gate.blocker_count, 0)
        self.assertTrue(
            verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate(
                gate
            ).accepted
        )

    def test_gate_check_planes_and_required_semantics_are_conserved(self) -> None:
        gate = self._gate()
        self.assertEqual(
            {item.plane for item in gate.checks},
            {"linkage", "catalog", "runtime", "federation", "assurance", "public"},
        )
        self.assertEqual(
            gate.passed_count + gate.warning_count + gate.blocker_count, gate.check_count
        )
        self.assertEqual(sum(item.required for item in gate.checks), 10)
        self.assertEqual([item.ordinal for item in gate.checks], list(range(gate.check_count)))

    def test_gate_json_csv_markdown_are_deterministic(self) -> None:
        gate = self._gate()
        document = json.loads(
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate_json(
                gate
            )
        )
        self.assertEqual(document["content_address"], gate.content_address)
        rows = list(
            csv.DictReader(
                module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate_csv(
                    gate
                ).splitlines()
            )
        )
        self.assertEqual(len(rows), gate.check_count)
        markdown = render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate_markdown(
            gate
        )
        self.assertIn("Durable Review-Store Catalog Release Gate", markdown)
        self.assertIn("runtime-reconciled", markdown)

    def test_gate_query_filters_receipts_and_exports(self) -> None:
        gate = self._gate()
        result = query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate(
            gate, plane="linkage", required=True, passed=True, limit=20
        )
        self.assertEqual(result["total"], 4)
        self.assertTrue(
            verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate_query(
                result
            )
        )
        self.assertIn(
            "linkage",
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate_query_json(
                result
            ),
        )
        self.assertIn(
            "Gate Query",
            render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate_query_markdown(
                result
            ),
        )

    def test_gate_query_tampering_is_rejected(self) -> None:
        result = query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate(
            self._gate(), severity="pass"
        )
        result["items"] = []
        with self.assertRaises(ValidationError):
            verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate_query(
                result
            )

    def test_gate_schema_and_capabilities_are_identity_free(self) -> None:
        values = (
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate_schema(),
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate_capabilities(),
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate_query_schema(),
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate_query_capabilities(),
        )
        for value in values:
            encoded = json.dumps(value).casefold()
            self.assertNotIn("agent", encoded)
            self.assertNotIn("language", encoded)
        self.assertEqual(
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate_capabilities()[
                "combines"
            ],
            ["catalog", "runtime", "federation", "assurance"],
        )

    def test_gate_from_directory_recomputes_each_projection(self) -> None:
        catalog = self._ready()
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "catalog"
            write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
                catalog, destination
            )
            gate = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate_from_directory(
                destination
            )
            self.assertEqual(gate.state, "ready")
            self.assertEqual(gate.catalog_address, catalog.content_address)

    def test_gate_holds_a_valid_held_catalog(self) -> None:
        catalog = self._catalog(self._store("held", state="held", release_ready=False))
        gate = self._gate(catalog)
        self.assertEqual(gate.state, "held")
        self.assertTrue(gate.accepted)
        self.assertFalse(gate.release_ready)
        self.assertGreater(gate.warning_count, 0)
        self.assertEqual(gate.blocker_count, 0)

    def test_gate_blocks_rejected_catalog(self) -> None:
        catalog = self._catalog(
            self._store("blocked", state="blocked", release_ready=False, accepted=False)
        )
        gate = self._gate(catalog)
        self.assertEqual(gate.state, "blocked")
        self.assertFalse(gate.accepted)
        self.assertFalse(gate.release_ready)
        self.assertGreater(gate.blocker_count, 0)

    def test_gate_blocks_unknown_federation_selection(self) -> None:
        gate = self._gate(self._ready(), store_ids=("missing",))
        self.assertEqual(gate.state, "blocked")
        self.assertFalse(gate.accepted)
        self.assertFalse(
            next(item for item in gate.checks if item.kind == "federation-accepted").passed
        )

    def test_gate_holds_when_ready_threshold_is_not_met(self) -> None:
        catalog = self._catalog(
            self._store("ready"), self._store("held", state="held", release_ready=False)
        )
        gate = self._gate(catalog, minimum_members=2, minimum_ready=2)
        self.assertEqual(gate.state, "held")
        self.assertTrue(gate.accepted)
        self.assertFalse(gate.release_ready)
        self.assertEqual(gate.blocker_count, 0)

    def test_gate_accepts_mixed_window_as_held_when_policy_allows_it(self) -> None:
        catalog = self._catalog(
            self._store("alpha"), self._store("beta", window_address="window:two")
        )
        gate = self._gate(catalog, require_same_window=False, minimum_members=2, minimum_ready=2)
        self.assertEqual(gate.state, "held")
        self.assertTrue(gate.accepted)
        self.assertFalse(gate.release_ready)
        self.assertFalse(
            next(item for item in gate.checks if item.kind == "federation-release-ready").passed
        )

    def test_gate_address_is_stable_for_repeated_builds(self) -> None:
        left = self._gate()
        right = self._gate()
        self.assertEqual(left.to_dict(), right.to_dict())
        self.assertEqual(left.content_address, right.content_address)

    def test_gate_invalid_inputs_are_rejected(self) -> None:
        gate = self._gate()
        with self.assertRaises(ValidationError):
            query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate(
                gate, plane="unknown"
            )
        with self.assertRaises(ValidationError):
            query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate(
                gate, severity="unknown"
            )
        with self.assertRaises(ValidationError):
            query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate(
                gate, offset=-1
            )

    def test_gate_public_projection_contains_no_forbidden_attributes(self) -> None:
        for value in (self._assurance().to_dict(), self._gate().to_dict()):
            encoded = json.dumps(value).casefold()
            for forbidden in (
                "agent",
                "assistant",
                "author",
                "language",
                "model",
                "private",
                "secret",
                "token",
            ):
                self.assertNotIn(f'"{forbidden}"', encoded)

    def test_gate_runtime_reconciliation_accepts_only_a_readiness_stop(self) -> None:
        catalog = self._catalog(self._store("held", state="held", release_ready=False))
        gate = self._gate(catalog)
        runtime_check = next(item for item in gate.checks if item.kind == "runtime-reconciled")
        self.assertTrue(runtime_check.passed)
        self.assertTrue(
            next(item for item in gate.checks if item.kind == "runtime-release-ready").severity
            == "warning"
        )

    def test_assurance_and_gate_addresses_are_distinct_and_linked(self) -> None:
        catalog = self._ready()
        assurance = self._assurance(catalog)
        gate = self._gate(catalog)
        self.assertNotEqual(assurance.content_address, catalog.content_address)
        self.assertNotEqual(gate.content_address, assurance.content_address)
        self.assertEqual(gate.catalog_address, assurance.catalog_address)

    def test_assurance_to_dict_can_omit_findings_without_losing_summary(self) -> None:
        assurance = self._assurance()
        summary = assurance.to_dict(include_findings=False)
        self.assertNotIn("findings", summary)
        self.assertEqual(summary["finding_count"], assurance.finding_count)

    def test_gate_to_dict_can_omit_checks_without_losing_summary(self) -> None:
        gate = self._gate()
        summary = gate.to_dict(include_checks=False)
        self.assertNotIn("checks", summary)
        self.assertEqual(summary["check_count"], gate.check_count)

    def test_cli_entrypoints_build_assurance_and_gate(self) -> None:
        catalog = self._ready()
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "catalog"
            write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
                catalog, destination
            )
            assurance_output = Path(root) / "assurance.json"
            gate_output = Path(root) / "gate.json"
            assurance_result = main(
                [
                    "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-assurance",
                    "--catalog-directory",
                    str(destination),
                    "--format",
                    "summary",
                    "--output",
                    str(assurance_output),
                ]
            )
            gate_result = main(
                [
                    "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-gate",
                    "--catalog-directory",
                    str(destination),
                    "--format",
                    "summary",
                    "--output",
                    str(gate_output),
                ]
            )
            self.assertEqual(assurance_result, 0)
            self.assertEqual(gate_result, 0)
            self.assertEqual(json.loads(assurance_output.read_text())["state"], "passed")
            self.assertEqual(json.loads(gate_output.read_text())["state"], "ready")

    def test_http_routes_build_assurance_gate_and_queries(self) -> None:
        catalog = self._ready()
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "catalog"
            write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
                catalog, destination
            )
            server = create_server("127.0.0.1", 0, str(Path(root) / "data"))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = "/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog"
            try:
                cases = (
                    (
                        base + "/assurance",
                        {"catalog_directory": str(destination), "format": "summary"},
                        "passed",
                    ),
                    (
                        base + "/assurance/query",
                        {"catalog_directory": str(destination), "plane": "readiness"},
                        None,
                    ),
                    (
                        base + "/gate",
                        {"catalog_directory": str(destination), "format": "summary"},
                        "ready",
                    ),
                    (
                        base + "/gate/query",
                        {
                            "catalog_directory": str(destination),
                            "plane": "linkage",
                            "passed": "true",
                        },
                        None,
                    ),
                )
                for path, params, expected_state in cases:
                    connection = HTTPConnection("127.0.0.1", server.server_address[1], timeout=15)
                    connection.request("GET", path + "?" + urlencode(params))
                    response = connection.getresponse()
                    payload = json.loads(response.read().decode("utf-8"))
                    self.assertEqual(response.status, 200)
                    if expected_state is not None:
                        self.assertEqual(payload["state"], expected_state)
                    else:
                        self.assertGreaterEqual(payload["total"], 1)
                    connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
