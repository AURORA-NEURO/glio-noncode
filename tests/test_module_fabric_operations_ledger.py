"""Tests for the module-fabric operational ledger and recovery boundary."""

from __future__ import annotations

import json
import unittest
from dataclasses import replace

from glio_noncode.module_fabric_operations_ledger import (
    LEDGER_BOUNDARY,
    LEDGER_VERSION,
    RECOVERY_BOUNDARY,
    RECOVERY_VERSION,
    FabricLedgerEntry,
    FabricOperationLedger,
    audit_module_fabric_operation_ledger,
    build_module_fabric_operation_ledger,
    build_module_fabric_recovery_report,
    module_fabric_operation_ledger_json,
    module_fabric_recovery_json,
)
from glio_noncode.module_fabric_runtime import run_module_fabric_runtime
from glio_noncode.module_fabric_public_data import default_module_fabric_fixture


class ModuleFabricOperationsLedgerTests(unittest.TestCase):
    def test_canonical_ledger_has_twenty_ordered_entries(self) -> None:
        ledger = build_module_fabric_operation_ledger()
        self.assertEqual(LEDGER_VERSION, ledger.version)
        self.assertEqual(LEDGER_BOUNDARY, ledger.boundary)
        self.assertEqual(20, len(ledger.entries))
        self.assertEqual(tuple(range(1, 21)), tuple(item.ordinal for item in ledger.entries))
        self.assertEqual(32, ledger.record_count)
        self.assertEqual(16, ledger.accepted_records)
        self.assertEqual(16, ledger.review_records)
        self.assertEqual("release-decision", ledger.entries[-1].stage_id)

    def test_audit_closes_the_ledger(self) -> None:
        ledger = build_module_fabric_operation_ledger()
        audit = audit_module_fabric_operation_ledger(ledger)
        self.assertTrue(audit.accepted)
        self.assertEqual(10, len(audit.checks))
        self.assertEqual(10, audit.passed_checks)
        self.assertEqual(0, audit.failed_checks)

    def test_audit_can_reconcile_against_runtime(self) -> None:
        fixture = default_module_fabric_fixture()
        runtime = run_module_fabric_runtime(fixture)
        ledger = build_module_fabric_operation_ledger(fixture, run_id="reconcile")
        audit = audit_module_fabric_operation_ledger(ledger, runtime)
        self.assertTrue(audit.accepted)
        self.assertEqual(runtime.evaluation.fixture_id, ledger.fixture_id)

    def test_order_mutation_is_visible(self) -> None:
        ledger = build_module_fabric_operation_ledger()
        mutated_entries = (replace(ledger.entries[0], ordinal=2),) + ledger.entries[1:]
        mutated = replace(ledger, entries=mutated_entries)
        audit = audit_module_fabric_operation_ledger(mutated)
        self.assertFalse(audit.accepted)
        self.assertIn("ordinals-contiguous", {item.check_id for item in audit.checks if not item.passed})

    def test_record_count_mutation_is_visible(self) -> None:
        ledger = build_module_fabric_operation_ledger()
        mutated_entries = (replace(ledger.entries[3], record_count=31),) + ledger.entries[4:]
        mutated = replace(ledger, entries=mutated_entries)
        audit = audit_module_fabric_operation_ledger(mutated)
        self.assertFalse(audit.accepted)
        self.assertIn("record-count-conserved", {item.check_id for item in audit.checks if not item.passed})

    def test_recovery_queue_contains_controls_only(self) -> None:
        report = build_module_fabric_recovery_report()
        self.assertEqual(RECOVERY_VERSION, report.version)
        self.assertEqual(RECOVERY_BOUNDARY, report.boundary)
        self.assertTrue(report.accepted)
        self.assertEqual(16, len(report.items))
        self.assertEqual({"review"}, {item.current_state.value for item in report.items})
        self.assertTrue(all(not item.automatic_promotion for item in report.items))
        self.assertEqual(
            {"context_key", "declared_domain_id", "public_source_scope"},
            set(report.items[0].required_evidence),
        )

    def test_recovery_queue_is_stable(self) -> None:
        first = build_module_fabric_recovery_report()
        second = build_module_fabric_recovery_report()
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(
            tuple(item.content_address for item in first.items),
            tuple(item.content_address for item in second.items),
        )

    def test_json_outputs_are_parseable_and_sanitized(self) -> None:
        ledger_json = module_fabric_operation_ledger_json(build_module_fabric_operation_ledger())
        recovery_json = module_fabric_recovery_json(build_module_fabric_recovery_report())
        ledger = json.loads(ledger_json)
        recovery = json.loads(recovery_json)
        self.assertEqual(20, len(ledger["entries"]))
        self.assertEqual(16, len(recovery["items"]))
        self.assertNotIn("payload", ledger_json)
        self.assertNotIn("payload", recovery_json)

    def test_entry_rejects_non_positive_ordinal(self) -> None:
        with self.assertRaises(ValueError):
            FabricLedgerEntry(
                operation_id="bad",
                stage_id="bad",
                ordinal=0,
                state="accepted",
                accepted_records=0,
                review_records=0,
                record_count=0,
                input_address="input:1",
                output_address="output:1",
                detail="bad",
                content_address="entry:1",
            )

    def test_ledger_requires_entries(self) -> None:
        with self.assertRaises(ValueError):
            FabricOperationLedger(
                ledger_id="bad",
                version=LEDGER_VERSION,
                boundary=LEDGER_BOUNDARY,
                run_id="bad",
                fixture_id="bad",
                entries=(),
                final_state="accepted",
                accepted_records=0,
                review_records=0,
                record_count=1,
                content_address="ledger:1",
            )


if __name__ == "__main__":
    unittest.main()
