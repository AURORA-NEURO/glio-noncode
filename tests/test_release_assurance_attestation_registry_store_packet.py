"""Contract tests for portable registry-store packets."""

from __future__ import annotations

import json
import tempfile
import unittest
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread
from urllib.parse import urlencode

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
from glio_noncode.release_assurance_attestation_registry_store_packet import (
    build_release_assurance_attestation_registry_store_packet,
    load_release_assurance_attestation_registry_store_packet,
    release_assurance_attestation_registry_store_packet_artifact_payloads,
    verify_release_assurance_attestation_registry_store_packet,
    write_release_assurance_attestation_registry_store_packet,
)
from glio_noncode.release_assurance_attestation_registry_store_packet_contracts import (
    RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_PACKET_ARTIFACT_COUNT,
    RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_PACKET_PAYLOAD_COUNT,
    RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_PACKET_PAYLOAD_IDS,
)
from glio_noncode.release_assurance_attestation_runtime import run_release_assurance_attestation
from glio_noncode.release_assurance_runtime import run_release_assurance
from glio_noncode.service_surface import build_service_surface_snapshot


class ReleaseAssuranceAttestationRegistryStorePacketTests(unittest.TestCase):
    """Exercise packet closure, tamper controls, API, and CLI."""

    @classmethod
    def setUpClass(cls) -> None:
        service = build_service_surface_snapshot()
        source_runtime = run_release_assurance(
            service,
            bundle_id="registry-store-packet-source",
            run_id="registry-store-packet-source-run",
        )
        program = build_program_release_snapshot()
        catalog, catalog_gate = build_default_release_assurance_catalog_gate()
        first = run_release_assurance_attestation(
            source_runtime,
            program_release=program,
            catalog=catalog,
            catalog_gate=catalog_gate,
            attestation_id="registry-store-packet-first",
            bundle_id="registry-store-packet-first-bundle",
            run_id="registry-store-packet-first-run",
        ).attestation
        second = build_release_assurance_attestation(
            source_runtime,
            program_release=program,
            catalog=catalog,
            catalog_gate=catalog_gate,
            attestation_id="registry-store-packet-second",
            bundle_id="registry-store-packet-second-bundle",
            run_id="registry-store-packet-second-run",
        )
        registry = build_release_assurance_attestation_registry(
            [first], registry_id="registry-store-packet-test"
        )
        initial_store = build_release_assurance_attestation_registry_store(
            registry,
            store_id="registry-store-packet-test-store",
        )
        cls.store = append_release_assurance_attestation_registry_store(
            initial_store,
            second,
        ).store
        cls.first = first
        cls.second = second

    def test_packet_has_fixed_public_payload_set(self) -> None:
        packet = build_release_assurance_attestation_registry_store_packet(self.store)
        self.assertTrue(packet.accepted)
        self.assertEqual(
            len(packet.artifacts),
            RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_PACKET_PAYLOAD_COUNT,
        )
        self.assertEqual(
            packet.manifest.artifact_count,
            RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_PACKET_ARTIFACT_COUNT,
        )
        self.assertEqual(
            tuple(item.artifact_id for item in packet.artifacts),
            RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_PACKET_PAYLOAD_IDS,
        )
        payloads = release_assurance_attestation_registry_store_packet_artifact_payloads(self.store)
        self.assertEqual(
            set(payloads), set(RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_PACKET_PAYLOAD_IDS)
        )
        self.assertTrue(all(isinstance(item, bytes) for item in payloads.values()))

    def test_atomic_round_trip_and_hydration_require_acceptance(self) -> None:
        packet = build_release_assurance_attestation_registry_store_packet(self.store)
        with tempfile.TemporaryDirectory() as directory:
            write_release_assurance_attestation_registry_store_packet(packet, directory)
            verification = verify_release_assurance_attestation_registry_store_packet(directory)
            self.assertTrue(verification.accepted, verification.to_dict())
            self.assertEqual(
                verification.checked_artifact_count,
                RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_PACKET_PAYLOAD_COUNT,
            )
            offline = load_release_assurance_attestation_registry_store_packet(directory)
            self.assertEqual(offline.store, self.store)
            self.assertTrue(offline.verification.accepted)
            self.assertEqual(
                set(path.name for path in (Path(directory) / "store").iterdir()),
                {
                    "store.json",
                    "operations.csv",
                    "policy.json",
                    "head.json",
                    "audit.json",
                    "summary.json",
                    "schema.json",
                    "capabilities.json",
                },
            )

    def test_tamper_and_unexpected_file_controls_fail_closed(self) -> None:
        packet = build_release_assurance_attestation_registry_store_packet(self.store)
        with tempfile.TemporaryDirectory() as directory:
            write_release_assurance_attestation_registry_store_packet(packet, directory)
            target = Path(directory) / "store" / "store.json"
            target.write_bytes(target.read_bytes() + b" ")
            tampered = verify_release_assurance_attestation_registry_store_packet(directory)
            self.assertFalse(tampered.accepted)
            self.assertIn("store/store.json", tampered.tampered_paths)
        with tempfile.TemporaryDirectory() as directory:
            write_release_assurance_attestation_registry_store_packet(packet, directory)
            (Path(directory) / "unexpected.txt").write_text("unexpected\n", encoding="utf-8")
            unexpected = verify_release_assurance_attestation_registry_store_packet(directory)
            self.assertFalse(unexpected.accepted)
            self.assertIn("unexpected.txt", unexpected.unexpected_paths)
            with self.assertRaises(ValidationError):
                load_release_assurance_attestation_registry_store_packet(directory)

    def test_api_and_cli_packet_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            packet = build_release_assurance_attestation_registry_store_packet(self.store)
            write_release_assurance_attestation_registry_store_packet(packet, directory)
            server = create_server("127.0.0.1", 0, ".")
            server.glio_release_assurance_attestations = {
                ("registry-store-packet-api-bundle", "registry-store-packet-api-run"): self.first
            }
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                connection = HTTPConnection(host, port, timeout=30)
                connection.request(
                    "GET",
                    "/v1/release-assurance/attestation/registry/store/packet"
                    "?bundle_id=registry-store-packet-api-bundle"
                    "&run_id=registry-store-packet-api-run",
                )
                response = connection.getresponse()
                packet_payload = json.loads(response.read())
                self.assertEqual(response.status, 200)
                self.assertTrue(packet_payload["accepted"])
                self.assertEqual(len(packet_payload["artifacts"]), 8)

                query = urlencode({"directory": directory})
                connection.request(
                    "GET",
                    "/v1/release-assurance/attestation/registry/store/packet/verify?" + query,
                )
                response = connection.getresponse()
                verification = json.loads(response.read())
                self.assertEqual(response.status, 200)
                self.assertTrue(verification["accepted"])

                connection.request(
                    "GET",
                    "/v1/release-assurance/attestation/registry/store/packet/capabilities",
                )
                response = connection.getresponse()
                capabilities = json.loads(response.read())
                self.assertEqual(response.status, 200)
                self.assertTrue(capabilities["exact_byte_verification"])
            finally:
                server.shutdown()
                server.server_close()

            cli_output = str(Path(directory) / "cli-packet.json")
            cli_packet_dir = str(Path(directory) / "cli-packet")
            self.assertEqual(
                main(
                    [
                        "release-assurance-attestation",
                        "--plane",
                        "registry-store-packet",
                        "--registry-id",
                        "registry-store-packet-cli",
                        "--store-id",
                        "registry-store-packet-cli-store",
                        "--destination",
                        cli_packet_dir,
                        "--output",
                        cli_output,
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "release-assurance-attestation-registry-store-packet-verify",
                        cli_packet_dir,
                    ]
                ),
                0,
            )


if __name__ == "__main__":
    unittest.main()
