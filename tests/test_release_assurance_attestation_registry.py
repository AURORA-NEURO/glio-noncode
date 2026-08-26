"""Contract tests for longitudinal release-attestation registries."""

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
    audit_release_assurance_attestation_registry,
    build_release_assurance_attestation_registry,
    diff_release_assurance_attestation_registries,
    query_release_assurance_attestation_registry,
    release_assurance_attestation_registry_json,
    replay_release_assurance_attestation_registry,
)
from glio_noncode.release_assurance_attestation_registry_contracts import (
    RELEASE_ASSURANCE_ATTESTATION_REGISTRY_PACKET_ARTIFACT_COUNT,
    RELEASE_ASSURANCE_ATTESTATION_REGISTRY_PACKET_PAYLOAD_COUNT,
    RELEASE_ASSURANCE_ATTESTATION_REGISTRY_RESOURCE_NAMES,
    ReleaseAssuranceAttestationRegistry,
    ReleaseAssuranceAttestationRegistryTransitionState,
)
from glio_noncode.release_assurance_attestation_registry_packet import (
    build_release_assurance_attestation_registry_packet,
    load_release_assurance_attestation_registry_packet,
    verify_release_assurance_attestation_registry_packet,
    write_release_assurance_attestation_registry_packet,
)
from glio_noncode.release_assurance_attestation_runtime import run_release_assurance_attestation
from glio_noncode.release_assurance_runtime import run_release_assurance
from glio_noncode.release_assurance_support import forbidden_keys
from glio_noncode.service_surface import build_service_surface_snapshot


class ReleaseAssuranceAttestationRegistryTests(unittest.TestCase):
    """Exercise sequence, replay, query, diff, packet, and boundary controls."""

    @classmethod
    def setUpClass(cls) -> None:
        service = build_service_surface_snapshot()
        cls.source_runtime = run_release_assurance(
            service,
            bundle_id="registry-source",
            run_id="registry-source-run",
        )
        cls.program = build_program_release_snapshot()
        cls.catalog, cls.catalog_gate = build_default_release_assurance_catalog_gate()
        cls.first = run_release_assurance_attestation(
            cls.source_runtime,
            program_release=cls.program,
            catalog=cls.catalog,
            catalog_gate=cls.catalog_gate,
            attestation_id="registry-first",
            bundle_id="registry-first-bundle",
            run_id="registry-first-run",
        ).attestation
        cls.second = build_release_assurance_attestation(
            cls.source_runtime,
            program_release=cls.program,
            catalog=cls.catalog,
            catalog_gate=cls.catalog_gate,
            attestation_id="registry-second",
            bundle_id="registry-second-bundle",
            run_id="registry-second-run",
        )

    def test_single_registry_is_rooted_and_replayable(self) -> None:
        registry = build_release_assurance_attestation_registry(
            [self.first], registry_id="registry-test"
        )
        self.assertTrue(registry.accepted)
        self.assertEqual(registry.entry_count, 1)
        self.assertEqual(registry.transition_count, 0)
        self.assertEqual(registry.entries[0].previous_entry_address, "root")
        self.assertEqual(
            registry.entries[0].transition,
            ReleaseAssuranceAttestationRegistryTransitionState.INITIAL,
        )
        audits = audit_release_assurance_attestation_registry(registry, [self.first])
        self.assertTrue(all(item["passed"] for item in audits))
        replay = replay_release_assurance_attestation_registry(
            registry, (item for item in [self.first])
        )
        self.assertTrue(replay["deterministic"])
        self.assertTrue(replay["accepted"])
        hydrated = ReleaseAssuranceAttestationRegistry.from_mapping(
            json.loads(release_assurance_attestation_registry_json(registry))
        )
        self.assertEqual(hydrated, registry)
        self.assertEqual(forbidden_keys(registry.to_dict()), ())

    def test_sequence_transitions_queries_and_diff(self) -> None:
        registry = build_release_assurance_attestation_registry(
            [self.first, self.second], registry_id="registry-test"
        )
        self.assertTrue(registry.accepted)
        self.assertEqual(registry.entry_count, 2)
        self.assertEqual(registry.transition_count, 1)
        transition = registry.transitions[0]
        self.assertEqual(
            transition.state,
            ReleaseAssuranceAttestationRegistryTransitionState.ADVANCE,
        )
        self.assertEqual(transition.changed_summary_fields, ("bundle_id", "run_id"))
        entries = query_release_assurance_attestation_registry(
            registry, resource="entries", limit=1
        )
        self.assertEqual(entries.total, 2)
        self.assertTrue(entries.has_more)
        transitions = query_release_assurance_attestation_registry(
            registry,
            resource="transitions",
            transition_state="advance",
        )
        self.assertEqual(transitions.total, 1)
        self.assertEqual(
            set(RELEASE_ASSURANCE_ATTESTATION_REGISTRY_RESOURCE_NAMES), {"entries", "transitions"}
        )
        diff = diff_release_assurance_attestation_registries(
            build_release_assurance_attestation_registry([self.first], registry_id="registry-test"),
            registry,
        )
        self.assertTrue(diff.accepted)
        self.assertFalse(diff.identical)
        self.assertEqual(len(diff.added_entry_ids), 1)
        with self.assertRaises(ValidationError):
            query_release_assurance_attestation_registry(registry, resource="unknown")
        with self.assertRaises(ValidationError):
            query_release_assurance_attestation_registry(registry, limit=501)

    def test_exact_byte_registry_packet_and_tamper_controls(self) -> None:
        registry = build_release_assurance_attestation_registry(
            [self.first, self.second], registry_id="registry-packet-test"
        )
        packet = build_release_assurance_attestation_registry_packet(registry)
        self.assertTrue(packet.accepted)
        self.assertEqual(
            len(packet.artifacts), RELEASE_ASSURANCE_ATTESTATION_REGISTRY_PACKET_PAYLOAD_COUNT
        )
        self.assertEqual(
            packet.manifest.artifact_count,
            RELEASE_ASSURANCE_ATTESTATION_REGISTRY_PACKET_ARTIFACT_COUNT,
        )
        with tempfile.TemporaryDirectory() as directory:
            write_release_assurance_attestation_registry_packet(packet, directory)
            verification = verify_release_assurance_attestation_registry_packet(directory)
            self.assertTrue(verification.accepted)
            self.assertEqual(
                verification.checked_artifact_count,
                RELEASE_ASSURANCE_ATTESTATION_REGISTRY_PACKET_PAYLOAD_COUNT,
            )
            offline = load_release_assurance_attestation_registry_packet(directory)
            self.assertEqual(offline.registry, registry)
            target = Path(directory) / "registry" / "registry.json"
            target.write_bytes(target.read_bytes() + b" ")
            tampered = verify_release_assurance_attestation_registry_packet(directory)
            self.assertFalse(tampered.accepted)
            self.assertIn("registry/registry.json", tampered.tampered_paths)
        with tempfile.TemporaryDirectory() as directory:
            write_release_assurance_attestation_registry_packet(packet, directory)
            (Path(directory) / "extra.txt").write_text("extra\n", encoding="utf-8")
            unexpected = verify_release_assurance_attestation_registry_packet(directory)
            self.assertFalse(unexpected.accepted)
            self.assertIn("extra.txt", unexpected.unexpected_paths)

    def test_api_and_cli_registry_surfaces(self) -> None:
        server = create_server("127.0.0.1", 0, ".")
        server.glio_release_assurance_attestations = {
            ("registry-api-bundle", "registry-api-run"): self.first
        }
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = server.server_address
            connection = HTTPConnection(host, port, timeout=30)
            connection.request(
                "GET",
                "/v1/release-assurance/attestation/registry"
                "?bundle_id=registry-api-bundle&run_id=registry-api-run"
                "&registry_id=registry-api-test",
            )
            response = connection.getresponse()
            registry_payload = json.loads(response.read())
            self.assertEqual(response.status, 200)
            self.assertTrue(registry_payload["accepted"])
            self.assertEqual(registry_payload["entry_count"], 1)

            connection.request(
                "GET",
                "/v1/release-assurance/attestation/registry/query"
                "?bundle_id=registry-api-bundle&run_id=registry-api-run"
                "&resource=entries&limit=1",
            )
            response = connection.getresponse()
            query_payload = json.loads(response.read())
            self.assertEqual(response.status, 200)
            self.assertEqual(query_payload["total"], 1)
            self.assertEqual(len(query_payload["items"]), 1)

            connection.request("GET", "/v1/release-assurance/attestation/registry/capabilities")
            response = connection.getresponse()
            capabilities = json.loads(response.read())
            self.assertEqual(response.status, 200)
            self.assertIn("registry", capabilities)
            self.assertTrue(capabilities["packet"]["exact_byte_verification"])

            verify_body = json.dumps({"registry": registry_payload}).encode("utf-8")
            connection.request(
                "POST",
                "/v1/release-assurance/attestation/registry/verify",
                verify_body,
                {"Content-Type": "application/json"},
            )
            response = connection.getresponse()
            verified = json.loads(response.read())
            self.assertEqual(response.status, 200)
            self.assertTrue(verified["accepted"])

            query_body = json.dumps(
                {"registry": registry_payload, "query": {"resource": "entries"}}
            ).encode("utf-8")
            connection.request(
                "POST",
                "/v1/release-assurance/attestation/registry/query",
                query_body,
                {"Content-Type": "application/json"},
            )
            response = connection.getresponse()
            posted_query = json.loads(response.read())
            self.assertEqual(response.status, 200)
            self.assertEqual(posted_query["total"], 1)
        finally:
            server.shutdown()
            server.server_close()

        with tempfile.TemporaryDirectory() as directory:
            output = str(Path(directory) / "registry-query.json")
            self.assertEqual(
                main(
                    [
                        "release-assurance-attestation",
                        "--plane",
                        "registry-query",
                        "--registry-id",
                        "registry-cli-test",
                        "--registry-resource",
                        "entries",
                        "--limit",
                        "1",
                        "--output",
                        output,
                    ]
                ),
                0,
            )
            cli_payload = json.loads(Path(output).read_text(encoding="utf-8"))
            self.assertEqual(cli_payload["total"], 1)


if __name__ == "__main__":
    unittest.main()
