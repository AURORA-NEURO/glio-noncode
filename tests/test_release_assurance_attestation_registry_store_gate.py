"""Contract tests for deterministic registry-store promotion gates."""

from __future__ import annotations

import json
import tempfile
import unittest
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread

from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.program_release_closure_bundle import build_program_release_snapshot
from glio_noncode.release_assurance_attestation import (
    build_default_release_assurance_catalog_gate,
    build_release_assurance_attestation,
)
from glio_noncode.release_assurance_attestation_registry import (
    build_release_assurance_attestation_registry,
)
from glio_noncode.release_assurance_attestation_registry_store import (
    append_release_assurance_attestation_registry_store,
    build_release_assurance_attestation_registry_store,
)
from glio_noncode.release_assurance_attestation_registry_store_gate import (
    build_release_assurance_attestation_registry_store_gate_plan,
    build_release_assurance_attestation_registry_store_gate_policy,
    diff_release_assurance_attestation_registry_store_gate_state,
    evaluate_release_assurance_attestation_registry_store_gate,
    query_release_assurance_attestation_registry_store_gate,
)
from glio_noncode.release_assurance_attestation_registry_store_gate_contracts import (
    RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_EXPECTED_CHECK_COUNT,
    ReleaseAssuranceAttestationRegistryStoreGateDecision,
    ReleaseAssuranceAttestationRegistryStoreGateState,
)
from glio_noncode.release_assurance_attestation_runtime import run_release_assurance_attestation
from glio_noncode.release_assurance_runtime import run_release_assurance
from glio_noncode.service_surface import build_service_surface_snapshot


class ReleaseAssuranceAttestationRegistryStoreGateTests(unittest.TestCase):
    """Exercise the promotion denominator, preflight plan, API, and CLI."""

    @classmethod
    def setUpClass(cls) -> None:
        service = build_service_surface_snapshot()
        source_runtime = run_release_assurance(
            service,
            bundle_id="registry-store-gate-source",
            run_id="registry-store-gate-source-run",
        )
        program = build_program_release_snapshot()
        catalog, catalog_gate = build_default_release_assurance_catalog_gate()
        cls.first = run_release_assurance_attestation(
            source_runtime,
            program_release=program,
            catalog=catalog,
            catalog_gate=catalog_gate,
            attestation_id="registry-store-gate-first",
            bundle_id="registry-store-gate-first-bundle",
            run_id="registry-store-gate-first-run",
        ).attestation
        cls.second = build_release_assurance_attestation(
            source_runtime,
            program_release=program,
            catalog=catalog,
            catalog_gate=catalog_gate,
            attestation_id="registry-store-gate-second",
            bundle_id="registry-store-gate-second-bundle",
            run_id="registry-store-gate-second-run",
        )
        registry = build_release_assurance_attestation_registry(
            [cls.first], registry_id="registry-store-gate-test"
        )
        cls.initial_store = build_release_assurance_attestation_registry_store(
            registry,
            store_id="registry-store-gate-test-store",
        )
        cls.candidate_store = append_release_assurance_attestation_registry_store(
            cls.initial_store,
            cls.second,
        ).store

    def _policy(self, **overrides):
        values = {
            "gate_id": "registry-store-gate-test-policy",
            "store_id": self.candidate_store.store_id,
            "registry_id": self.candidate_store.registry.registry_id,
            "require_packet": False,
        }
        values.update(overrides)
        return build_release_assurance_attestation_registry_store_gate_policy(**values)

    def _server(self):
        server = create_server("127.0.0.1", 0, ".")
        server.glio_release_assurance_attestations = {
            ("registry-store-gate-api-bundle", "registry-store-gate-api-run"): self.first
        }
        return server

    @staticmethod
    def _json_request(connection, method, path, payload=None):
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {} if body is None else {"Content-Type": "application/json"}
        connection.request(method, path, body, headers)
        response = connection.getresponse()
        return response.status, json.loads(response.read())

    def test_ready_gate_closes_twenty_checks_and_round_trips(self) -> None:
        gate = evaluate_release_assurance_attestation_registry_store_gate(
            self.candidate_store,
            policy=self._policy(),
            baseline=self.initial_store,
        )
        self.assertTrue(gate.accepted, gate.to_dict())
        self.assertEqual(gate.state, ReleaseAssuranceAttestationRegistryStoreGateState.READY)
        self.assertEqual(
            gate.decision,
            ReleaseAssuranceAttestationRegistryStoreGateDecision.PROMOTE,
        )
        self.assertEqual(
            gate.check_count,
            RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_EXPECTED_CHECK_COUNT,
        )
        self.assertEqual(gate.passed_check_count, gate.check_count)
        self.assertEqual(gate.failed_check_ids, ())
        self.assertEqual(gate.critical_failure_count, 0)
        self.assertEqual(gate.boundary, "public_longitudinal_release_registry_store_gate")
        round_trip = gate.from_mapping(gate.to_dict())
        self.assertEqual(round_trip, gate)

    def test_default_packet_requirement_blocks_without_verified_packet(self) -> None:
        gate = evaluate_release_assurance_attestation_registry_store_gate(
            self.candidate_store,
            policy=self._policy(require_packet=True),
            baseline=self.initial_store,
        )
        self.assertFalse(gate.accepted)
        self.assertEqual(gate.state, ReleaseAssuranceAttestationRegistryStoreGateState.HOLD)
        self.assertEqual(
            gate.decision,
            ReleaseAssuranceAttestationRegistryStoreGateDecision.RETAIN,
        )
        self.assertIn("packet-verification", gate.failed_check_ids)
        result = query_release_assurance_attestation_registry_store_gate(
            gate,
            failed_only=True,
            category="packet",
            limit=10,
        )
        self.assertEqual(result.total, 1)
        self.assertEqual(len(result.items), 1)
        self.assertFalse(result.items[0]["passed"])
        self.assertFalse(result.accepted)

    def test_diff_and_preflight_plan_preserve_sequence_continuity(self) -> None:
        diff = diff_release_assurance_attestation_registry_store_gate_state(
            self.initial_store,
            self.candidate_store,
        )
        self.assertTrue(diff.accepted)
        self.assertTrue(diff.continuous)
        self.assertFalse(diff.identical)
        self.assertTrue(diff.changed_head)
        self.assertEqual(diff.added_entry_count, 1)
        self.assertEqual(diff.removed_entry_count, 0)
        self.assertEqual(diff.changed_entry_count, 0)
        self.assertEqual(diff.added_operation_count, 1)
        self.assertEqual(diff.removed_operation_count, 0)

        plan = build_release_assurance_attestation_registry_store_gate_plan(
            self.initial_store,
            self.second,
            policy=self._policy(),
            expected_head_address=self.initial_store.head_address,
        )
        self.assertTrue(plan.accepted, plan.to_dict())
        self.assertEqual(plan.proposed_action, "append-and-promote")
        self.assertEqual(plan.current_store_address, self.initial_store.content_address)
        self.assertEqual(plan.expected_head_address, self.initial_store.head_address)
        self.assertEqual(plan.candidate_attestation_id, self.second.attestation_id)
        expected_gate = evaluate_release_assurance_attestation_registry_store_gate(
            self.candidate_store,
            policy=self._policy(),
            baseline=self.initial_store,
        )
        self.assertEqual(plan.gate_address, expected_gate.content_address)

        stale_plan = build_release_assurance_attestation_registry_store_gate_plan(
            self.initial_store,
            self.second,
            policy=self._policy(),
            expected_head_address="stale-head-address",
        )
        self.assertFalse(stale_plan.accepted)
        self.assertEqual(stale_plan.proposed_action, "retain-and-review")

    def test_policy_limits_and_contract_tampering_fail_closed(self) -> None:
        limited = evaluate_release_assurance_attestation_registry_store_gate(
            self.candidate_store,
            policy=self._policy(max_entries=1),
            baseline=self.initial_store,
        )
        self.assertFalse(limited.accepted)
        self.assertIn("policy-entry-capacity", limited.failed_check_ids)
        self.assertEqual(limited.state, ReleaseAssuranceAttestationRegistryStoreGateState.HOLD)

        payload = limited.to_dict()
        payload["checks"][0]["content_address"] = "tampered"
        with self.assertRaises(ValidationError):
            limited.from_mapping(payload)

        policy_payload = self._policy().to_dict()
        policy_payload["max_operations"] = 0
        policy_payload.pop("content_address")
        with self.assertRaises(ValidationError):
            build_release_assurance_attestation_registry_store_gate_policy(**policy_payload)

    def test_api_gate_surfaces_expose_schema_evaluation_query_and_diff(self) -> None:
        server = self._server()
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = server.server_address
            connection = HTTPConnection(host, port, timeout=30)
            status, capabilities = self._json_request(
                connection,
                "GET",
                "/v1/release-assurance/attestation/registry/store/gate/capabilities",
            )
            self.assertEqual(status, 200)
            self.assertEqual(capabilities["fixed_check_count"], 20)

            status, schema = self._json_request(
                connection,
                "GET",
                "/v1/release-assurance/attestation/registry/store/gate/schema",
            )
            self.assertEqual(status, 200)
            self.assertTrue(schema["version"].endswith("-v1"))
            self.assertIn("checks", schema["required"])

            status, blocked = self._json_request(
                connection,
                "GET",
                "/v1/release-assurance/attestation/registry/store/gate"
                "?bundle_id=registry-store-gate-api-bundle&run_id=registry-store-gate-api-run",
            )
            self.assertEqual(status, 422)
            self.assertFalse(blocked["accepted"])
            self.assertIn("packet-verification", blocked["failed_check_ids"])

            store_payload = self.initial_store.to_dict()
            policy_payload = self._policy().to_dict()
            status, evaluated = self._json_request(
                connection,
                "POST",
                "/v1/release-assurance/attestation/registry/store/gate/evaluate",
                {"store": self.candidate_store.to_dict(), "policy": policy_payload},
            )
            self.assertEqual(status, 200)
            self.assertTrue(evaluated["accepted"])
            self.assertEqual(evaluated["check_count"], 20)

            status, verified = self._json_request(
                connection,
                "POST",
                "/v1/release-assurance/attestation/registry/store/gate/verify",
                {"gate": evaluated},
            )
            self.assertEqual(status, 200)
            self.assertTrue(verified["accepted"])

            status, queried = self._json_request(
                connection,
                "POST",
                "/v1/release-assurance/attestation/registry/store/gate/query",
                {"gate": evaluated, "query": {"category": "integrity", "limit": 3}},
            )
            self.assertEqual(status, 200)
            self.assertEqual(queried["total"], 6)
            self.assertEqual(len(queried["items"]), 3)
            self.assertTrue(queried["has_more"])

            status, plan = self._json_request(
                connection,
                "POST",
                "/v1/release-assurance/attestation/registry/store/gate/plan",
                {
                    "store": self.initial_store.to_dict(),
                    "attestation": self.second.to_dict(),
                    "policy": policy_payload,
                },
            )
            self.assertEqual(status, 200)
            self.assertTrue(plan["accepted"])

            status, diff = self._json_request(
                connection,
                "POST",
                "/v1/release-assurance/attestation/registry/store/gate/diff",
                {"baseline": store_payload, "candidate": self.candidate_store.to_dict()},
            )
            self.assertEqual(status, 200)
            self.assertTrue(diff["continuous"])
            self.assertEqual(diff["added_entry_count"], 1)
        finally:
            server.shutdown()
            server.server_close()

    def test_cli_gate_build_query_plan_and_diff(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            gate_output = root / "gate.json"
            query_output = root / "query.json"
            plan_output = root / "plan.json"
            diff_output = root / "diff.json"
            common = [
                "release-assurance-attestation",
                "--registry-id",
                "registry-store-gate-cli",
                "--store-id",
                "registry-store-gate-cli-store",
                "--gate-no-packet",
            ]
            self.assertEqual(
                main(common + ["--plane", "registry-store-gate", "--output", str(gate_output)]),
                0,
            )
            gate_payload = json.loads(gate_output.read_text(encoding="utf-8"))
            self.assertTrue(gate_payload["accepted"])
            self.assertEqual(gate_payload["check_count"], 20)

            self.assertEqual(
                main(
                    common
                    + [
                        "--plane",
                        "registry-store-gate-query",
                        "--failed-only",
                        "--output",
                        str(query_output),
                    ]
                ),
                0,
            )
            query_payload = json.loads(query_output.read_text(encoding="utf-8"))
            self.assertEqual(query_payload["total"], 0)
            self.assertFalse(query_payload["items"])

            self.assertEqual(
                main(
                    common
                    + [
                        "--plane",
                        "registry-store-gate-plan",
                        "--output",
                        str(plan_output),
                    ]
                ),
                0,
            )
            plan_payload = json.loads(plan_output.read_text(encoding="utf-8"))
            self.assertTrue(plan_payload["accepted"])
            self.assertEqual(plan_payload["proposed_action"], "append-and-promote")

            self.assertEqual(
                main(
                    common
                    + [
                        "--plane",
                        "registry-store-gate-diff",
                        "--output",
                        str(diff_output),
                    ]
                ),
                0,
            )
            diff_payload = json.loads(diff_output.read_text(encoding="utf-8"))
            self.assertTrue(diff_payload["accepted"])
            self.assertTrue(diff_payload["continuous"])
            self.assertEqual(diff_payload["added_entry_count"], 1)


if __name__ == "__main__":
    unittest.main()
