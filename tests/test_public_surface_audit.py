"""Contract tests for the repository-wide public-surface audit."""

from __future__ import annotations

import json
import tempfile
import unittest
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread

from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.public_surface_audit import (
    PUBLIC_SURFACE_EXPECTED_COUNT,
    build_default_public_surface_audit,
    build_public_surface_audit,
)


class PublicSurfaceAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.audit = build_default_public_surface_audit()

    def test_default_inventory_is_closed_and_accepted(self) -> None:
        self.assertTrue(self.audit.accepted)
        self.assertEqual(self.audit.surface_count, PUBLIC_SURFACE_EXPECTED_COUNT)
        self.assertEqual(self.audit.passed_surface_count, PUBLIC_SURFACE_EXPECTED_COUNT)
        self.assertEqual(self.audit.failed_surface_count, 0)
        self.assertEqual(self.audit.failed_surface_ids, ())
        self.assertTrue(self.audit.content_address.startswith("public-surface-audit:"))
        self.assertTrue(all(item.content_address.startswith("public-surface-audit-check:") for item in self.audit.checks))

    def test_schema_declarations_are_allowed_but_runtime_attribution_is_not(self) -> None:
        schema_check = next(item for item in self.audit.checks if item.surface_id == "service-schema")
        self.assertTrue(schema_check.accepted)
        self.assertEqual(schema_check.violation_paths, ())

        surfaces = {f"service-{index:02d}": {"value": index} for index in range(13)}
        surfaces["service-bad"] = {"agent_id": "forbidden"}
        result = build_public_surface_audit(surfaces)
        self.assertFalse(result.accepted)
        bad_check = next(item for item in result.checks if item.surface_id == "service-bad")
        self.assertFalse(bad_check.accepted)
        self.assertIn("$.agent_id", bad_check.violation_paths)

    def test_inventory_closes_the_durable_service_release_handoff(self) -> None:
        handoff = next(
            item
            for item in self.audit.checks
            if item.surface_id == "service-release-handoff"
        )
        self.assertTrue(handoff.accepted)
        self.assertEqual(handoff.violation_paths, ())

    def test_inventory_closes_deployment_profile_and_schema(self) -> None:
        for surface_id in ("deployment-profile", "deployment-profile-schema"):
            check = next(item for item in self.audit.checks if item.surface_id == surface_id)
            self.assertTrue(check.accepted, check.to_dict())
            self.assertEqual(check.violation_paths, ())

    def test_inventory_closes_reference_manifest_and_schema(self) -> None:
        for surface_id in ("reference-manifest", "reference-manifest-schema"):
            check = next(item for item in self.audit.checks if item.surface_id == surface_id)
            self.assertTrue(check.accepted, check.to_dict())
            self.assertEqual(check.violation_paths, ())

    def test_inventory_closes_streaming_intake_contracts(self) -> None:
        for surface_id in (
            "streaming-intake-schema",
            "streaming-intake-capabilities",
            "breakend-normalization-schema",
        ):
            check = next(item for item in self.audit.checks if item.surface_id == surface_id)
            self.assertTrue(check.accepted, check.to_dict())
            self.assertEqual(check.violation_paths, ())

    def test_inventory_closes_reference_interval_index_contracts(self) -> None:
        for surface_id in ("reference-index-schema", "reference-index-capabilities"):
            check = next(item for item in self.audit.checks if item.surface_id == surface_id)
            self.assertTrue(check.accepted, check.to_dict())
            self.assertEqual(check.violation_paths, ())

    def test_inventory_closes_declared_reference_adapter_contracts(self) -> None:
        for surface_id in ("reference-adapter-schema", "reference-adapter-capabilities"):
            check = next(item for item in self.audit.checks if item.surface_id == surface_id)
            self.assertTrue(check.accepted, check.to_dict())
            self.assertEqual(check.violation_paths, ())

    def test_inventory_closes_cohort_benchmark_contracts(self) -> None:
        for surface_id in ("cohort-benchmark-schema", "cohort-benchmark-capabilities"):
            check = next(item for item in self.audit.checks if item.surface_id == surface_id)
            self.assertTrue(check.accepted, check.to_dict())
            self.assertEqual(check.violation_paths, ())

    def test_inventory_closes_review_workspace_contracts(self) -> None:
        for surface_id in (
            "review-workspace-schema",
            "review-workspace-capabilities",
            "review-workspace-plan-schema",
            "review-workspace-plan-capabilities",
            "review-workspace-plan-execution-schema",
            "review-workspace-plan-execution-capabilities",
            "review-workspace-plan-execution-release-schema",
            "review-workspace-plan-execution-release-capabilities",
            "review-workspace-plan-execution-transitions-schema",
            "review-workspace-plan-execution-transitions-capabilities",
            "review-workspace-plan-execution-transitions-diff-schema",
            "review-workspace-plan-execution-transitions-diff-capabilities",
            "review-workspace-plan-execution-simulation-schema",
            "review-workspace-plan-execution-simulation-capabilities",
            "review-workspace-plan-execution-batch-schema",
            "review-workspace-plan-execution-batch-capabilities",
            "review-workspace-plan-execution-audit-schema",
            "review-workspace-plan-execution-audit-capabilities",
            "mission-plan-schema",
            "mission-plan-capabilities",
            "mission-plan-release-schema",
            "mission-plan-release-capabilities",
            "mission-plan-release-query-schema",
            "mission-plan-release-query-capabilities",
            "mission-plan-release-diff-schema",
            "mission-plan-release-diff-capabilities",
            "mission-plan-release-runtime-schema",
            "mission-plan-release-runtime-capabilities",
            "mission-plan-release-observability-schema",
            "mission-plan-release-observability-capabilities",
            "mission-plan-release-lineage-schema",
            "mission-plan-release-lineage-capabilities",
            "mission-plan-release-policy-schema",
            "mission-plan-release-policy-capabilities",
            "mission-plan-release-catalog-schema",
            "mission-plan-release-catalog-capabilities",
            "mission-plan-release-catalog-query-schema",
            "mission-plan-release-catalog-query-capabilities",
            "mission-plan-release-catalog-diff-schema",
            "mission-plan-release-catalog-diff-capabilities",
            "mission-plan-release-catalog-audit-schema",
            "mission-plan-release-catalog-audit-capabilities",
            "mission-plan-release-catalog-report-schema",
            "mission-plan-release-catalog-report-capabilities",
            "mission-plan-release-catalog-gate-schema",
            "mission-plan-release-catalog-gate-capabilities",
            "mission-plan-release-catalog-gate-runtime-schema",
            "mission-plan-release-catalog-gate-runtime-capabilities",
            "mission-plan-release-catalog-gate-packet-schema",
            "mission-plan-release-catalog-gate-packet-capabilities",
            "mission-plan-release-catalog-gate-query-schema",
            "mission-plan-release-catalog-gate-query-capabilities",
            "mission-plan-release-catalog-gate-diff-schema",
            "mission-plan-release-catalog-gate-diff-capabilities",
            "mission-plan-release-catalog-gate-observability-schema",
            "mission-plan-release-catalog-gate-observability-capabilities",
            "release-assurance-attestation-schema",
            "release-assurance-attestation-capabilities",
            "release-assurance-attestation-runtime-capabilities",
            "release-assurance-attestation-packet-schema",
            "release-assurance-attestation-packet-capabilities",
            "release-assurance-attestation-query-schema",
            "release-assurance-attestation-query-capabilities",
            "release-assurance-attestation-diff-schema",
            "release-assurance-attestation-diff-capabilities",
            "release-assurance-attestation-observability-schema",
            "release-assurance-attestation-observability-capabilities",
            "release-assurance-attestation-review-schema",
            "release-assurance-attestation-review-capabilities",
            "release-assurance-attestation-registry-schema",
            "release-assurance-attestation-registry-capabilities",
            "release-assurance-attestation-registry-packet-schema",
            "release-assurance-attestation-registry-packet-capabilities",
            "release-assurance-attestation-registry-store-schema",
            "release-assurance-attestation-registry-store-capabilities",
            "release-assurance-attestation-registry-store-packet-schema",
            "release-assurance-attestation-registry-store-packet-capabilities",
            "release-assurance-attestation-registry-store-gate-schema",
            "release-assurance-attestation-registry-store-gate-capabilities",
            "release-assurance-attestation-registry-store-gate-packet-schema",
            "release-assurance-attestation-registry-store-gate-packet-capabilities",
            "storage-maintenance-schema",
            "storage-maintenance-capabilities",
            "storage-maintenance-packet-schema",
            "storage-maintenance-packet-capabilities",
            "storage-maintenance-observability-schema",
            "storage-maintenance-observability-capabilities",
            "storage-maintenance-review-schema",
            "storage-maintenance-review-capabilities",
            "storage-lineage-schema",
            "storage-lineage-capabilities",
            "storage-lineage-observability-schema",
            "storage-lineage-observability-capabilities",
            "storage-lineage-review-schema",
            "storage-lineage-review-capabilities",
            "storage-lineage-packet-schema",
            "storage-lineage-packet-capabilities",
            "storage-catalog-schema",
            "storage-catalog-capabilities",
            "storage-catalog-observability-schema",
            "storage-catalog-observability-capabilities",
            "storage-catalog-packet-schema",
            "storage-catalog-packet-capabilities",
            "mission-plan-conformance-schema",
            "mission-plan-conformance-capabilities",
            "mission-plan-replay-schema",
            "mission-plan-replay-capabilities",
        ):
            check = next(item for item in self.audit.checks if item.surface_id == surface_id)
            self.assertTrue(check.accepted, check.to_dict())
            self.assertEqual(check.violation_paths, ())

    def test_cli_writes_accepted_audit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = f"{directory}/public-surface-audit.json"
            self.assertEqual(main(["public-surface-audit", "--output", output]), 0)
            payload = json.loads(Path(output).read_text(encoding="utf-8"))
            self.assertTrue(payload["accepted"])
            self.assertEqual(payload["surface_count"], PUBLIC_SURFACE_EXPECTED_COUNT)

    def test_http_endpoint_returns_audited_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            server = create_server("127.0.0.1", 0, directory)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                connection = HTTPConnection(host, port, timeout=60)
                connection.request("GET", "/v1/public-surface/audit")
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                payload = json.loads(response.read())
                self.assertTrue(payload["accepted"])
                self.assertEqual(payload["surface_count"], PUBLIC_SURFACE_EXPECTED_COUNT)
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
