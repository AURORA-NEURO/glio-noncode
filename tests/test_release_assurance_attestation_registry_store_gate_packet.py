"""Contract tests for portable promotion-gate decision packets."""

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
)
from glio_noncode.release_assurance_attestation_registry import (
    build_release_assurance_attestation_registry,
)
from glio_noncode.release_assurance_attestation_registry_store import (
    build_release_assurance_attestation_registry_store,
)
from glio_noncode.release_assurance_attestation_registry_store_gate import (
    build_release_assurance_attestation_registry_store_gate_policy,
    evaluate_release_assurance_attestation_registry_store_gate,
)
from glio_noncode.release_assurance_attestation_registry_store_gate_packet import (
    build_release_assurance_attestation_registry_store_gate_packet,
    load_release_assurance_attestation_registry_store_gate_packet,
    release_assurance_attestation_registry_store_gate_packet_artifact_payloads,
    verify_release_assurance_attestation_registry_store_gate_packet,
    write_release_assurance_attestation_registry_store_gate_packet,
)
from glio_noncode.release_assurance_attestation_registry_store_gate_packet_contracts import (
    RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_PACKET_ARTIFACT_COUNT,
    RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_PACKET_PAYLOAD_COUNT,
    RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_PACKET_PAYLOAD_IDS,
)
from glio_noncode.release_assurance_attestation_runtime import run_release_assurance_attestation
from glio_noncode.release_assurance_runtime import run_release_assurance
from glio_noncode.service_surface import build_service_surface_snapshot


class ReleaseAssuranceAttestationRegistryStoreGatePacketTests(unittest.TestCase):
    """Exercise packet closure, exact bytes, hydration, API, and CLI."""

    @classmethod
    def setUpClass(cls) -> None:
        service = build_service_surface_snapshot()
        source_runtime = run_release_assurance(
            service,
            bundle_id="registry-store-gate-packet-source",
            run_id="registry-store-gate-packet-source-run",
        )
        program = build_program_release_snapshot()
        catalog, catalog_gate = build_default_release_assurance_catalog_gate()
        attestation = run_release_assurance_attestation(
            source_runtime,
            program_release=program,
            catalog=catalog,
            catalog_gate=catalog_gate,
            attestation_id="registry-store-gate-packet-attestation",
            bundle_id="registry-store-gate-packet-bundle",
            run_id="registry-store-gate-packet-run",
        ).attestation
        registry = build_release_assurance_attestation_registry(
            [attestation], registry_id="registry-store-gate-packet-test"
        )
        store = build_release_assurance_attestation_registry_store(
            registry,
            store_id="registry-store-gate-packet-test-store",
        )
        policy = build_release_assurance_attestation_registry_store_gate_policy(
            gate_id="registry-store-gate-packet-test-gate",
            store_id=store.store_id,
            registry_id=store.registry.registry_id,
            require_packet=False,
        )
        cls.gate = evaluate_release_assurance_attestation_registry_store_gate(
            store,
            policy=policy,
        )

    @staticmethod
    def _json_request(connection, method, path, payload=None):
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {} if body is None else {"Content-Type": "application/json"}
        connection.request(method, path, body, headers)
        response = connection.getresponse()
        return response.status, json.loads(response.read())

    def test_packet_has_fixed_gate_payload_set_and_addressed_metadata(self) -> None:
        packet = build_release_assurance_attestation_registry_store_gate_packet(self.gate)
        self.assertTrue(packet.accepted)
        self.assertEqual(packet.gate_id, self.gate.gate_id)
        self.assertEqual(packet.manifest.gate_address, self.gate.content_address)
        self.assertEqual(
            len(packet.artifacts),
            RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_PACKET_PAYLOAD_COUNT,
        )
        self.assertEqual(
            packet.manifest.artifact_count,
            RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_PACKET_ARTIFACT_COUNT,
        )
        self.assertEqual(
            tuple(item.artifact_id for item in packet.artifacts),
            RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_PACKET_PAYLOAD_IDS,
        )
        payloads = release_assurance_attestation_registry_store_gate_packet_artifact_payloads(
            self.gate.to_dict()
        )
        self.assertEqual(
            set(payloads), set(RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_PACKET_PAYLOAD_IDS)
        )
        self.assertTrue(all(isinstance(value, bytes) for value in payloads.values()))
        self.assertFalse(any("content" in artifact for artifact in packet.to_dict()["artifacts"]))

    def test_atomic_round_trip_and_offline_hydration_require_acceptance(self) -> None:
        packet = build_release_assurance_attestation_registry_store_gate_packet(self.gate)
        with tempfile.TemporaryDirectory() as directory:
            write_release_assurance_attestation_registry_store_gate_packet(packet, directory)
            verification = verify_release_assurance_attestation_registry_store_gate_packet(
                directory
            )
            self.assertTrue(verification.accepted, verification.to_dict())
            self.assertEqual(verification.checked_artifact_count, 6)
            offline = load_release_assurance_attestation_registry_store_gate_packet(directory)
            self.assertEqual(offline.gate, self.gate)
            self.assertTrue(offline.verification.accepted)
            self.assertEqual(
                set(path.name for path in (Path(directory) / "gate").iterdir()),
                {
                    "gate.json",
                    "checks.csv",
                    "policy.json",
                    "summary.json",
                    "schema.json",
                    "capabilities.json",
                },
            )
            with self.assertRaises(ValidationError):
                write_release_assurance_attestation_registry_store_gate_packet(packet, directory)

    def test_tamper_and_unexpected_file_controls_fail_closed(self) -> None:
        packet = build_release_assurance_attestation_registry_store_gate_packet(self.gate)
        with tempfile.TemporaryDirectory() as directory:
            write_release_assurance_attestation_registry_store_gate_packet(packet, directory)
            target = Path(directory) / "gate" / "gate.json"
            target.write_bytes(target.read_bytes() + b" ")
            tampered = verify_release_assurance_attestation_registry_store_gate_packet(directory)
            self.assertFalse(tampered.accepted)
            self.assertIn("gate/gate.json", tampered.tampered_paths)
            with self.assertRaises(ValidationError):
                load_release_assurance_attestation_registry_store_gate_packet(directory)
        with tempfile.TemporaryDirectory() as directory:
            write_release_assurance_attestation_registry_store_gate_packet(packet, directory)
            (Path(directory) / "extra.txt").write_text("extra\n", encoding="utf-8")
            unexpected = verify_release_assurance_attestation_registry_store_gate_packet(directory)
            self.assertFalse(unexpected.accepted)
            self.assertIn("extra.txt", unexpected.unexpected_paths)

    def test_api_packet_capabilities_schema_packet_and_verification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            packet = build_release_assurance_attestation_registry_store_gate_packet(self.gate)
            write_release_assurance_attestation_registry_store_gate_packet(packet, directory)
            server = create_server("127.0.0.1", 0, ".")
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                connection = HTTPConnection(host, port, timeout=30)
                status, capabilities = self._json_request(
                    connection,
                    "GET",
                    "/v1/release-assurance/attestation/registry/store/gate/packet/capabilities",
                )
                self.assertEqual(status, 200)
                self.assertTrue(capabilities["exact_byte_verification"])
                self.assertEqual(capabilities["payload_count"], 6)
                status, schema = self._json_request(
                    connection,
                    "GET",
                    "/v1/release-assurance/attestation/registry/store/gate/packet/schema",
                )
                self.assertEqual(status, 200)
                self.assertEqual(schema["payload_count"], 6)
                self.assertIn("gate_id", schema["required"])
                status, verification = self._json_request(
                    connection,
                    "GET",
                    "/v1/release-assurance/attestation/registry/store/gate/packet/verify"
                    + "?directory="
                    + directory.replace("\\", "/"),
                )
                self.assertEqual(status, 200)
                self.assertTrue(verification["accepted"])
                status, posted = self._json_request(
                    connection,
                    "POST",
                    "/v1/release-assurance/attestation/registry/store/gate/packet/verify",
                    {"directory": directory},
                )
                self.assertEqual(status, 200)
                self.assertTrue(posted["accepted"])
            finally:
                server.shutdown()
                server.server_close()

    def test_cli_gate_packet_build_and_verification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            packet_directory = root / "gate-packet"
            output = root / "gate-packet.json"
            verification = root / "gate-verification.json"
            self.assertEqual(
                main(
                    [
                        "release-assurance-attestation",
                        "--plane",
                        "registry-store-gate-packet",
                        "--registry-id",
                        "registry-store-gate-packet-cli",
                        "--store-id",
                        "registry-store-gate-packet-cli-store",
                        "--gate-no-packet",
                        "--destination",
                        str(packet_directory),
                        "--output",
                        str(output),
                    ]
                ),
                0,
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertTrue(payload["accepted"])
            self.assertEqual(len(payload["artifacts"]), 6)
            self.assertEqual(
                main(
                    [
                        "release-assurance-attestation-registry-store-gate-packet-verify",
                        str(packet_directory),
                        "--output",
                        str(verification),
                    ]
                ),
                0,
            )
            receipt = json.loads(verification.read_text(encoding="utf-8"))
            self.assertTrue(receipt["accepted"])
            self.assertEqual(receipt["checked_artifact_count"], 6)


if __name__ == "__main__":
    unittest.main()
