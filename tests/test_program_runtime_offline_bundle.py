"""Deep contract tests for the architecture-program offline handoff."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from glio_noncode.program_runtime_offline_audit import (
    audit_program_runtime_offline_bundle,
    audit_program_runtime_offline_directory,
    verify_program_runtime_offline_bundle,
)
from glio_noncode.program_runtime_offline_boundary import (
    audit_program_runtime_offline_boundary,
    program_runtime_offline_key_inventory,
)
from glio_noncode.program_runtime_offline_bundle import (
    build_program_runtime_offline_bundle,
    load_program_runtime_offline_bundle,
    write_program_runtime_offline_bundle,
)
from glio_noncode.program_runtime_offline_certification import (
    certify_program_runtime_offline_bundle,
)
from glio_noncode.program_runtime_offline_contracts import (
    PROGRAM_RUNTIME_OFFLINE_ARTIFACT_COUNT,
    PROGRAM_RUNTIME_OFFLINE_DOMAIN_COUNT,
    PROGRAM_RUNTIME_OFFLINE_PROGRAM_CHECK_COUNT,
    PROGRAM_RUNTIME_OFFLINE_RUNTIME_STAGE_COUNT,
)
from glio_noncode.program_runtime_offline_indexes import (
    audit_program_runtime_offline_indexes,
    build_program_runtime_offline_indexes,
)
from glio_noncode.program_runtime_offline_query import (
    diff_program_runtime_offline_bundles,
    query_program_runtime_offline_bundle,
)
from glio_noncode.program_runtime_offline_observability import (
    audit_program_runtime_offline_observability,
    build_program_runtime_offline_observability,
)
from glio_noncode.program_runtime_offline_reconciliation import (
    reconcile_program_runtime_offline_bundle,
)
from glio_noncode.program_runtime_offline_runtime import run_program_runtime_offline_runtime
from glio_noncode.program_runtime_offline_schema import (
    program_runtime_offline_bundle_schema,
    validate_program_runtime_offline_manifest,
)
from glio_noncode.program_runtime_offline_summary import (
    audit_program_runtime_offline_summary,
    build_program_runtime_offline_summary,
)


class ProgramRuntimeOfflineBundleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundle = build_program_runtime_offline_bundle(
            bundle_id="test-architecture-program-bundle",
            run_id="test-architecture-program-runtime",
        )

    def test_manifest_is_ready_and_conserves_source_denominators(self) -> None:
        self.assertTrue(self.bundle.ready)
        self.assertEqual(self.bundle.artifact_count, PROGRAM_RUNTIME_OFFLINE_ARTIFACT_COUNT)
        self.assertEqual(self.bundle.domain_count, PROGRAM_RUNTIME_OFFLINE_DOMAIN_COUNT)
        self.assertEqual(self.bundle.stage_count, PROGRAM_RUNTIME_OFFLINE_RUNTIME_STAGE_COUNT)
        self.assertEqual(self.bundle.failed_check_count, 0)
        self.assertTrue(self.bundle.content_address.startswith("program-runtime-offline-bundle:"))

    def test_artifacts_are_exact_byte_addressed(self) -> None:
        for artifact in self.bundle.artifacts:
            self.assertIsNotNone(artifact.payload)
            assert artifact.payload is not None
            self.assertEqual(artifact.byte_count, len(artifact.payload.encode("utf-8")))
            self.assertEqual(artifact.line_count, len(artifact.payload.splitlines()))
            self.assertTrue(
                artifact.content_address.startswith("program-runtime-offline-artifact:")
            )

    def test_audit_closes_bytes_joins_and_public_keys(self) -> None:
        audit = audit_program_runtime_offline_bundle(self.bundle)
        self.assertTrue(audit.accepted, audit.to_dict())
        self.assertEqual(audit.failed_check_count, 0)
        boundary = audit_program_runtime_offline_boundary(self.bundle)
        self.assertTrue(boundary["accepted"], boundary)
        inventory = program_runtime_offline_key_inventory(self.bundle)
        self.assertTrue(inventory["accepted"], inventory)
        self.assertEqual(inventory["forbidden_keys"], ())

    def test_query_resources_are_bounded_and_addressed(self) -> None:
        domains = query_program_runtime_offline_bundle(
            self.bundle,
            resource="domains",
            accepted_only=True,
            limit=4,
        )
        self.assertTrue(domains.accepted)
        self.assertEqual(domains.total, PROGRAM_RUNTIME_OFFLINE_DOMAIN_COUNT)
        self.assertEqual(len(domains.items), 4)
        self.assertTrue(domains.content_address.startswith("program-runtime-offline-query:"))
        one = query_program_runtime_offline_bundle(self.bundle, resource="domains", domain_id="D08")
        self.assertEqual(len(one.items), 1)
        self.assertEqual(one.items[0]["domain_id"], "D08")
        checks = query_program_runtime_offline_bundle(self.bundle, resource="checks", limit=500)
        self.assertEqual(checks.total, PROGRAM_RUNTIME_OFFLINE_PROGRAM_CHECK_COUNT)
        stages = query_program_runtime_offline_bundle(self.bundle, resource="stages", limit=500)
        self.assertEqual(stages.total, PROGRAM_RUNTIME_OFFLINE_RUNTIME_STAGE_COUNT)

    def test_indexes_and_reconciliation_close(self) -> None:
        indexes = build_program_runtime_offline_indexes(self.bundle)
        self.assertTrue(indexes.accepted, indexes.to_dict())
        index_audit = audit_program_runtime_offline_indexes(self.bundle, indexes)
        self.assertTrue(index_audit.accepted, index_audit.to_dict())
        self.assertEqual(indexes.resource_counts["domains"], PROGRAM_RUNTIME_OFFLINE_DOMAIN_COUNT)
        reconciliation = reconcile_program_runtime_offline_bundle(self.bundle)
        self.assertTrue(reconciliation.accepted, reconciliation.to_dict())
        self.assertEqual(reconciliation.failed_check_ids, ())

    def test_summary_and_certification_close(self) -> None:
        summary = build_program_runtime_offline_summary(self.bundle)
        summary_audit = audit_program_runtime_offline_summary(summary)
        self.assertTrue(summary_audit.accepted, summary_audit.to_dict())
        self.assertEqual(summary.counter_map["domain_count"], PROGRAM_RUNTIME_OFFLINE_DOMAIN_COUNT)
        self.assertEqual(
            summary.counter_map["program_check_count"], PROGRAM_RUNTIME_OFFLINE_PROGRAM_CHECK_COUNT
        )
        certification = certify_program_runtime_offline_bundle(self.bundle)
        self.assertTrue(certification.accepted, certification.to_dict())
        self.assertEqual(certification.check_count, 36)
        self.assertEqual(certification.coverage_percent, 100.0)
        self.assertEqual(certification.failed_check_ids, ())
        self.assertEqual(len(certification.domains), 7)
        self.assertTrue(all(item.accepted for item in certification.domains))

    def test_observability_stream_and_metrics_are_closed(self) -> None:
        report = build_program_runtime_offline_observability(self.bundle)
        audit = audit_program_runtime_offline_observability(report)
        self.assertTrue(report.accepted, report.to_dict())
        self.assertTrue(audit["accepted"], audit)
        self.assertEqual(report.event_count, 24)
        self.assertEqual(report.metric_count, 12)
        self.assertEqual(
            [item.sequence for item in report.events],
            list(range(1, report.event_count + 1)),
        )

    def test_schema_is_closed_and_accepts_manifest_projection(self) -> None:
        schema = program_runtime_offline_bundle_schema()
        self.assertEqual(schema["denominators"]["domains"], PROGRAM_RUNTIME_OFFLINE_DOMAIN_COUNT)
        manifest = self.bundle.to_dict(include_payloads=False)
        validation = validate_program_runtime_offline_manifest(manifest)
        self.assertTrue(validation["accepted"], validation)
        self.assertGreater(validation["check_count"], 10)

    def test_filesystem_materialization_and_reopen_verification(self) -> None:
        with tempfile.TemporaryDirectory(prefix="glio-program-offline-") as directory:
            destination = Path(directory) / "bundle"
            write_program_runtime_offline_bundle(self.bundle, destination)
            self.assertTrue((destination / "bundle.json").is_file())
            self.assertEqual(
                len([path for path in destination.rglob("*") if path.is_file()]),
                PROGRAM_RUNTIME_OFFLINE_ARTIFACT_COUNT + 1,
            )
            reopened = load_program_runtime_offline_bundle(destination, include_payloads=True)
            self.assertEqual(reopened.content_address, self.bundle.content_address)
            self.assertEqual(reopened.artifact_count, self.bundle.artifact_count)
            verification = verify_program_runtime_offline_bundle(destination)
            self.assertTrue(verification.accepted, verification.to_dict())
            directory_audit = audit_program_runtime_offline_directory(destination)
            self.assertTrue(directory_audit.accepted, directory_audit.to_dict())

    def test_diff_is_stable_for_two_equivalent_bundles(self) -> None:
        other = build_program_runtime_offline_bundle(
            bundle_id=self.bundle.bundle_id,
            run_id=self.bundle.run_id,
        )
        diff = diff_program_runtime_offline_bundles(self.bundle, other)
        self.assertTrue(diff.accepted, diff.to_dict())
        self.assertEqual(diff.changed_artifact_ids, ())
        self.assertEqual(diff.changed_counts, {})

    def test_runtime_closes_all_offline_stages(self) -> None:
        runtime = run_program_runtime_offline_runtime(
            bundle_id="test-runtime-bundle",
            run_id="test-runtime-run",
        )
        self.assertTrue(runtime.accepted, runtime.to_dict())
        self.assertEqual(runtime.state.value, "ready")
        self.assertEqual(len(runtime.stages), 11)
        self.assertTrue(all(item.state.value == "ready" for item in runtime.stages))
        self.assertTrue(runtime.replay.deterministic)
        self.assertTrue(runtime.certification.accepted)


if __name__ == "__main__":
    unittest.main()
