"""Focused regression coverage for D490 ledger-diff runtime registries."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode import downloaded_data_quality_d489_gate_decision_ledger_diff_runtime as runtime_model
from glio_noncode import downloaded_data_quality_d489_gate_decision_ledger_diff_runtime_audit as runtime_audit_model
from glio_noncode import downloaded_data_quality_d490_ledger_diff_runtime_registry as registry_model
from glio_noncode import downloaded_data_quality_d490_ledger_diff_runtime_registry_audit as audit_model
from glio_noncode import downloaded_data_quality_d490_ledger_diff_runtime_registry_query as query_model
from glio_noncode import downloaded_data_quality_d490_ledger_diff_runtime_registry_query_audit as query_audit_model
from glio_noncode.errors import ValidationError
from glio_noncode.serialization import canonical_json
from tests.test_downloaded_data_quality_d489 import _diff


def _runtimes() -> tuple[runtime_model.LedgerDiffRuntime, runtime_model.LedgerDiffRuntime]:
    diff = _diff()
    strict = runtime_model.run_runtime(diff, runtime_id="d490-strict-runtime", policy=runtime_model.build_policy("d490-strict-policy", diff.diff_id, maximum_added=0, maximum_removed=0, maximum_changed=0, allowed_directions=("improved",), require_accepted=True, require_state_change=True, allow_unchanged=True))
    release = runtime_model.run_runtime(diff, runtime_id="d490-release-runtime", policy=runtime_model.build_policy("d490-release-policy", diff.diff_id, maximum_added=1, maximum_removed=0, maximum_changed=0, allowed_directions=("improved",), require_accepted=True, require_state_change=True, allow_unchanged=True))
    return strict, release


class D490LedgerDiffRuntimeRegistryTests(unittest.TestCase):
    def test_registry_audit_query_and_exact_persistence(self) -> None:
        strict, release = _runtimes()
        strict_audit = runtime_audit_model.audit_runtime(strict)
        release_audit = runtime_audit_model.audit_runtime(release)
        policy = registry_model.build_policy("d490-controlled-policy", minimum_runtimes=2, minimum_ready=1, maximum_blocked=1, require_same_diff=True, require_same_direction=True, require_audited=True, require_release_ready=False)
        registry = registry_model.run_registry((strict, release), registry_id="d490-controlled-registry", policy=policy, audit_addresses={strict.runtime_id: strict_audit.content_address, release.runtime_id: release_audit.content_address})
        audit = audit_model.audit_registry(registry, (strict, release))
        query = query_model.query_registry(registry, resources=query_model.RESOURCES, limit=query_model.MAX_LIMIT)
        query_audit = query_audit_model.audit_query(query, registry)
        self.assertTrue(registry.release_ready)
        self.assertEqual((registry.ready_count, registry.blocked_count, registry.audited_count), (1, 1, 2))
        self.assertEqual((audit.check_count, audit.passed_count, audit.accepted), (16, 16, True))
        self.assertEqual((query_audit.check_count, query_audit.passed_count, query_audit.accepted), (12, 12, True))
        self.assertFalse(query.truncated)
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "registry"
            registry_model.persist_registry(registry, destination)
            self.assertEqual(tuple(sorted(path.name for path in destination.iterdir())), tuple(sorted(registry_model.FILES)))
            loaded = registry_model.load_registry(destination)
            self.assertEqual(loaded.content_address, registry.content_address)
            document = json.loads((destination / "registry.json").read_text(encoding="utf-8"))
            document["release_ready"] = False
            (destination / "registry.json").write_text(canonical_json(document), encoding="utf-8")
            with self.assertRaises(ValidationError):
                registry_model.load_registry(destination)

    def test_all_ready_policy_reports_controlled_failures(self) -> None:
        strict, release = _runtimes()
        policy = registry_model.build_policy("d490-all-ready-policy", minimum_runtimes=2, minimum_ready=2, maximum_blocked=0, require_same_diff=True, require_same_direction=True, require_audited=False, require_release_ready=True)
        registry = registry_model.build_registry((strict, release), registry_id="d490-all-ready-registry", policy=policy)
        self.assertFalse(registry.release_ready)
        self.assertEqual({item.check_id for item in registry.checks if not item.passed}, {"minimum_ready", "blocked_budget", "release_ready_policy", "public_boundary"} - {"public_boundary"})

    def test_duplicate_runtime_identity_and_address_are_rejected_by_checks(self) -> None:
        _, release = _runtimes()
        registry = registry_model.build_registry((release, release), registry_id="d490-duplicate-registry", policy=registry_model.build_policy("d490-duplicate-policy", minimum_runtimes=2, minimum_ready=1, maximum_blocked=1, require_same_diff=True, require_same_direction=True, require_audited=False, require_release_ready=False))
        self.assertFalse(registry.release_ready)
        self.assertEqual({item.check_id for item in registry.checks if not item.passed}, {"unique_runtime_ids", "unique_runtime_addresses"})


if __name__ == "__main__":
    unittest.main()
