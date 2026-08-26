"""Contract tests for the final cross-plane release-assurance attestation."""

from __future__ import annotations

import json
import tempfile
import unittest
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread

from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.mission_plan_release_catalog_gate import MissionPlanReleaseCatalogGate
from glio_noncode.program_release_closure_bundle import build_program_release_snapshot
from glio_noncode.release_assurance_attestation import (
    build_default_release_assurance_catalog_gate,
    build_release_assurance_attestation,
    release_assurance_attestation_capabilities,
    release_assurance_attestation_csv,
    release_assurance_attestation_json,
    release_assurance_attestation_markdown,
    release_assurance_attestation_schema,
    validate_release_assurance_attestation_schema,
)
from glio_noncode.release_assurance_attestation_contracts import (
    RELEASE_ASSURANCE_ATTESTATION_CHECK_COUNT,
    RELEASE_ASSURANCE_ATTESTATION_COMPONENT_COUNT,
    RELEASE_ASSURANCE_ATTESTATION_COMPONENT_IDS,
    RELEASE_ASSURANCE_ATTESTATION_RUNTIME_STAGE_TOTAL,
    ReleaseAssuranceAttestation,
    ReleaseAssuranceAttestationPolicy,
)
from glio_noncode.release_assurance_attestation_diff import diff_release_assurance_attestations
from glio_noncode.release_assurance_attestation_observability import (
    audit_release_assurance_attestation_observability,
    build_release_assurance_attestation_observability,
)
from glio_noncode.release_assurance_attestation_packet import (
    build_release_assurance_attestation_packet,
    load_release_assurance_attestation_packet,
    verify_release_assurance_attestation_packet,
    write_release_assurance_attestation_packet,
)
from glio_noncode.release_assurance_attestation_query import query_release_assurance_attestation
from glio_noncode.release_assurance_attestation_review import (
    ReleaseAssuranceAttestationReview,
    audit_release_assurance_attestation_review,
    build_release_assurance_attestation_review,
    query_release_assurance_attestation_review,
    release_assurance_attestation_review_json,
)
from glio_noncode.release_assurance_attestation_runtime import run_release_assurance_attestation
from glio_noncode.release_assurance_runtime import run_release_assurance
from glio_noncode.service_surface import build_service_surface_snapshot
from glio_noncode.release_assurance_support import forbidden_keys


class ReleaseAssuranceAttestationTests(unittest.TestCase):
    """Exercise every public plane without copying source records."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.service = build_service_surface_snapshot()
        cls.base_runtime = run_release_assurance(cls.service, bundle_id="attestation-source", run_id="attestation-source-run")
        cls.program = build_program_release_snapshot()
        cls.catalog, cls.catalog_gate = build_default_release_assurance_catalog_gate()
        cls.runtime = run_release_assurance_attestation(
            cls.base_runtime,
            program_release=cls.program,
            catalog=cls.catalog,
            catalog_gate=cls.catalog_gate,
            attestation_id="attestation-test",
            bundle_id="attestation-test-bundle",
            run_id="attestation-test-run",
        )
        cls.attestation = cls.runtime.attestation

    def test_fixed_denominators_dependency_order_and_boundary(self) -> None:
        self.assertTrue(self.attestation.accepted)
        self.assertEqual(self.attestation.component_count, RELEASE_ASSURANCE_ATTESTATION_COMPONENT_COUNT)
        self.assertEqual(self.attestation.check_count, RELEASE_ASSURANCE_ATTESTATION_CHECK_COUNT)
        self.assertEqual(self.attestation.passed_check_count, RELEASE_ASSURANCE_ATTESTATION_CHECK_COUNT)
        self.assertEqual(tuple(item.component_id for item in self.attestation.components), RELEASE_ASSURANCE_ATTESTATION_COMPONENT_IDS)
        self.assertEqual(self.attestation.overall_percent, 100.0)
        self.assertEqual(forbidden_keys(self.attestation.to_dict()), ())
        self.assertEqual(tuple(item.dependency_ids for item in self.attestation.components), ((), ("release-assurance",), ("program-release-closure",)))

    def test_policy_mapping_is_strict_and_addressed(self) -> None:
        policy = ReleaseAssuranceAttestationPolicy.from_mapping(ReleaseAssuranceAttestationPolicy().to_dict())
        self.assertEqual(policy.content_address, ReleaseAssuranceAttestationPolicy().content_address)
        with self.assertRaises(Exception):
            ReleaseAssuranceAttestationPolicy.from_mapping({"require_all_checks_passed": "false"})
        with self.assertRaises(Exception):
            ReleaseAssuranceAttestationPolicy.from_mapping({"unexpected": True})

    def test_schema_exports_and_round_trip(self) -> None:
        schema = release_assurance_attestation_schema()
        audits = validate_release_assurance_attestation_schema(self.attestation, schema)
        self.assertTrue(all(item.passed for item in audits))
        hydrated = ReleaseAssuranceAttestation.from_mapping(json.loads(release_assurance_attestation_json(self.attestation)))
        self.assertEqual(hydrated, self.attestation)
        self.assertIn(b"row_type", release_assurance_attestation_csv(self.attestation).encode("utf-8"))
        self.assertIn("# Release assurance attestation", release_assurance_attestation_markdown(self.attestation))
        self.assertTrue(release_assurance_attestation_capabilities()["cross_plane_binding"])

    def test_runtime_has_eight_ready_stages_and_replay(self) -> None:
        self.assertTrue(self.runtime.accepted)
        self.assertEqual(len(self.runtime.stages), RELEASE_ASSURANCE_ATTESTATION_RUNTIME_STAGE_TOTAL)
        self.assertTrue(all(item.state.value == "ready" for item in self.runtime.stages))
        self.assertTrue(self.runtime.replay.deterministic)
        self.assertEqual(self.runtime.replay.first_address, self.runtime.replay.second_address)
        self.assertEqual(self.runtime.replay.expected_address, self.attestation.content_address)

    def test_bounded_queries_filter_and_page(self) -> None:
        components = query_release_assurance_attestation(self.attestation, resource="components", limit=2)
        self.assertEqual(components.total, 3)
        self.assertTrue(components.has_more)
        checks = query_release_assurance_attestation(self.attestation, resource="checks", component_id="program-release-closure", passed_only=True)
        self.assertEqual(checks.total, 6)
        self.assertTrue(all(item["passed"] for item in checks.items))
        with self.assertRaises(Exception):
            query_release_assurance_attestation(self.attestation, resource="unknown")
        with self.assertRaises(Exception):
            query_release_assurance_attestation(self.attestation, limit=501)

    def test_address_only_diff_detects_policy_and_source_changes(self) -> None:
        comparison = build_release_assurance_attestation(
            self.base_runtime,
            program_release=self.program,
            catalog=self.catalog,
            catalog_gate=self.catalog_gate,
            attestation_id="attestation-comparison",
            bundle_id="attestation-comparison-bundle",
            run_id="attestation-comparison-run",
        )
        diff = diff_release_assurance_attestations(self.attestation, comparison)
        self.assertTrue(diff.accepted)
        self.assertFalse(diff.identical)
        self.assertEqual(diff.added_component_ids, ())
        self.assertEqual(diff.removed_component_ids, ())
        self.assertEqual(len(diff.unchanged_component_ids), 3)
        self.assertEqual(len(diff.changed_policy_fields), 0)
        identical = diff_release_assurance_attestations(self.attestation, self.attestation)
        self.assertTrue(identical.identical)

    def test_observability_conserves_counts_and_is_public(self) -> None:
        report = build_release_assurance_attestation_observability(self.attestation, self.runtime)
        self.assertTrue(report.accepted)
        self.assertEqual(len({item.metric_id for item in report.metrics}), len(report.metrics))
        metric_map = {item.metric_id: item.value for item in report.metrics}
        self.assertEqual(metric_map["attestation:component-count"], 3)
        self.assertEqual(metric_map["attestation:check-count"], RELEASE_ASSURANCE_ATTESTATION_CHECK_COUNT)
        self.assertEqual(metric_map["attestation:passed-check-count"], RELEASE_ASSURANCE_ATTESTATION_CHECK_COUNT)
        audits = audit_release_assurance_attestation_observability(report, self.attestation)
        self.assertTrue(all(item["passed"] for item in audits))
        self.assertEqual(forbidden_keys(report.to_dict()), ())

    def test_review_closes_every_check_and_routes_actions(self) -> None:
        review = build_release_assurance_attestation_review(self.attestation, runtime=self.runtime)
        self.assertTrue(review.accepted)
        self.assertEqual(review.item_count, RELEASE_ASSURANCE_ATTESTATION_CHECK_COUNT)
        self.assertEqual(review.open_action_count, 0)
        self.assertEqual(review.closed_action_count, RELEASE_ASSURANCE_ATTESTATION_CHECK_COUNT)
        self.assertEqual(review.failed_item_ids, ())
        self.assertTrue(all(item.disposition == "retain" for item in review.items))
        self.assertTrue(all(item.action_state == "closed" for item in review.items))
        audits = audit_release_assurance_attestation_review(review, self.attestation, runtime=self.runtime)
        self.assertTrue(all(item["passed"] for item in audits))
        self.assertEqual(forbidden_keys(review.to_dict()), ())
        hydrated = ReleaseAssuranceAttestationReview.from_mapping(
            json.loads(release_assurance_attestation_review_json(review))
        )
        self.assertEqual(hydrated.to_dict(), review.to_dict())

    def test_review_query_is_bounded_and_deterministic(self) -> None:
        review = build_release_assurance_attestation_review(self.attestation)
        result = query_release_assurance_attestation_review(
            review,
            component_id="program-release-closure",
            action_state="closed",
            limit=2,
        )
        self.assertEqual(result["total"], 6)
        self.assertEqual(len(result["items"]), 2)
        self.assertTrue(result["has_more"])
        self.assertTrue(all(item["component_id"] == "program-release-closure" for item in result["items"]))
        failed = query_release_assurance_attestation_review(review, failed_only=True)
        self.assertEqual(failed["total"], 0)
        with self.assertRaises(Exception):
            query_release_assurance_attestation_review(review, limit=1001)

    def test_exact_byte_packet_hydration_tamper_and_extra_file_controls(self) -> None:
        packet = build_release_assurance_attestation_packet(self.runtime)
        self.assertTrue(packet.accepted)
        self.assertEqual(len(packet.artifacts), 7)
        with tempfile.TemporaryDirectory() as directory:
            write_release_assurance_attestation_packet(packet, directory)
            verification = verify_release_assurance_attestation_packet(directory)
            self.assertTrue(verification.accepted)
            self.assertEqual(verification.checked_artifact_count, 7)
            offline = load_release_assurance_attestation_packet(directory)
            self.assertEqual(offline.attestation, self.attestation)
            target = Path(directory) / "attestation" / "attestation.json"
            target.write_bytes(target.read_bytes() + b" ")
            tampered = verify_release_assurance_attestation_packet(directory)
            self.assertFalse(tampered.accepted)
            self.assertIn("attestation/attestation.json", tampered.tampered_paths)
        with tempfile.TemporaryDirectory() as directory:
            write_release_assurance_attestation_packet(packet, directory)
            (Path(directory) / "unexpected.txt").write_text("unexpected\n", encoding="utf-8")
            unexpected = verify_release_assurance_attestation_packet(directory)
            self.assertFalse(unexpected.accepted)
            self.assertIn("unexpected.txt", unexpected.unexpected_paths)

    def test_api_get_post_and_cli_capability_paths(self) -> None:
        server = create_server("127.0.0.1", 0, ".")
        server.glio_release_assurance_attestations = {("attestation-api-bundle", "attestation-api-run"): self.attestation}
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = server.server_address
            connection = HTTPConnection(host, port, timeout=20)
            connection.request("GET", "/v1/release-assurance/attestation?bundle_id=attestation-api-bundle&run_id=attestation-api-run")
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            self.assertTrue(json.loads(response.read())["accepted"])
            connection.request(
                "GET",
                "/v1/release-assurance/attestation/review?bundle_id=attestation-api-bundle&run_id=attestation-api-run",
            )
            response = connection.getresponse()
            review_payload = json.loads(response.read())
            self.assertEqual(response.status, 200)
            self.assertTrue(review_payload["accepted"])
            self.assertEqual(review_payload["closed_action_count"], RELEASE_ASSURANCE_ATTESTATION_CHECK_COUNT)
            connection.request(
                "GET",
                "/v1/release-assurance/attestation/review/query?bundle_id=attestation-api-bundle&run_id=attestation-api-run&component_id=program-release-closure&limit=2",
            )
            response = connection.getresponse()
            review_query_payload = json.loads(response.read())
            self.assertEqual(response.status, 200)
            self.assertEqual(review_query_payload["total"], 6)
            self.assertEqual(len(review_query_payload["items"]), 2)
            body = json.dumps({"attestation": self.attestation.to_dict()}).encode("utf-8")
            connection.request("POST", "/v1/release-assurance/attestation/verify", body, {"Content-Type": "application/json"})
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            self.assertTrue(json.loads(response.read())["accepted"])
            review_body = json.dumps(
                {"review": build_release_assurance_attestation_review(self.attestation).to_dict()}
            ).encode("utf-8")
            connection.request(
                "POST",
                "/v1/release-assurance/attestation/review/query",
                review_body,
                {"Content-Type": "application/json"},
            )
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            self.assertEqual(json.loads(response.read())["total"], RELEASE_ASSURANCE_ATTESTATION_CHECK_COUNT)
            connection.request(
                "POST",
                "/v1/release-assurance/attestation/review",
                body,
                {"Content-Type": "application/json"},
            )
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            self.assertTrue(json.loads(response.read())["accepted"])
        finally:
            server.shutdown()
            server.server_close()
        with tempfile.TemporaryDirectory() as directory:
            output = str(Path(directory) / "capabilities.json")
            self.assertEqual(main(["release-assurance-attestation", "--plane", "capabilities", "--output", output]), 0)
            self.assertTrue(json.loads(Path(output).read_text(encoding="utf-8"))["packet"]["verify"])


if __name__ == "__main__":
    unittest.main()
