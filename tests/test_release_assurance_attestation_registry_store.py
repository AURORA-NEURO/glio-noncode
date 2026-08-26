"""Contract tests for append-only registry-store operations."""

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
    append_release_assurance_attestation_registry_store_batch,
    audit_release_assurance_attestation_registry_store,
    build_release_assurance_attestation_registry_store,
    build_release_assurance_attestation_registry_store_policy,
    diff_release_assurance_attestation_registry_stores,
    query_release_assurance_attestation_registry_store_operations,
    release_assurance_attestation_registry_store_json,
    replay_release_assurance_attestation_registry_store,
    verify_release_assurance_attestation_registry_store,
)
from glio_noncode.release_assurance_attestation_registry_store_contracts import (
    ReleaseAssuranceAttestationRegistryStoreDisposition,
    ReleaseAssuranceAttestationRegistryStoreState,
)
from glio_noncode.release_assurance_attestation_runtime import run_release_assurance_attestation
from glio_noncode.release_assurance_runtime import run_release_assurance
from glio_noncode.service_surface import build_service_surface_snapshot


class ReleaseAssuranceAttestationRegistryStoreTests(unittest.TestCase):
    """Exercise policy, append, retry, batch, replay, API, and CLI paths."""

    @classmethod
    def setUpClass(cls) -> None:
        service = build_service_surface_snapshot()
        source_runtime = run_release_assurance(
            service,
            bundle_id="registry-store-source",
            run_id="registry-store-source-run",
        )
        program = build_program_release_snapshot()
        catalog, catalog_gate = build_default_release_assurance_catalog_gate()
        cls.first = run_release_assurance_attestation(
            source_runtime,
            program_release=program,
            catalog=catalog,
            catalog_gate=catalog_gate,
            attestation_id="registry-store-first",
            bundle_id="registry-store-first-bundle",
            run_id="registry-store-first-run",
        ).attestation
        cls.second = build_release_assurance_attestation(
            source_runtime,
            program_release=program,
            catalog=catalog,
            catalog_gate=catalog_gate,
            attestation_id="registry-store-second",
            bundle_id="registry-store-second-bundle",
            run_id="registry-store-second-run",
        )
        cls.same_id = build_release_assurance_attestation(
            source_runtime,
            program_release=program,
            catalog=catalog,
            catalog_gate=catalog_gate,
            attestation_id="registry-store-first",
            bundle_id="registry-store-different-bundle",
            run_id="registry-store-different-run",
        )

    def _store(self):
        registry = build_release_assurance_attestation_registry(
            [self.first], registry_id="registry-store-test"
        )
        return build_release_assurance_attestation_registry_store(
            registry,
            store_id="registry-store-test-store",
        )

    def test_initial_store_is_addressed_and_public(self) -> None:
        store = self._store()
        self.assertTrue(store.accepted)
        self.assertEqual(store.operation_count, 0)
        self.assertEqual(store.head_address, store.registry.latest_entry.content_address)
        audit = audit_release_assurance_attestation_registry_store(store)
        self.assertTrue(audit.accepted, audit.to_dict())
        self.assertEqual(audit.failed_check_ids, ())
        hydrated = verify_release_assurance_attestation_registry_store(
            json.loads(release_assurance_attestation_registry_store_json(store))
        )
        self.assertTrue(hydrated.accepted)

    def test_append_updates_head_and_is_idempotent_on_retry(self) -> None:
        store = self._store()
        result = append_release_assurance_attestation_registry_store(
            store,
            self.second,
            expected_head_address=store.head_address,
        )
        self.assertTrue(result.accepted)
        self.assertEqual(
            result.operation.disposition,
            ReleaseAssuranceAttestationRegistryStoreDisposition.APPENDED,
        )
        self.assertEqual(result.store.registry.entry_count, 2)
        self.assertEqual(result.store.append_count, 1)
        retry = append_release_assurance_attestation_registry_store(
            result.store,
            self.second,
            expected_head_address=result.store.head_address,
        )
        self.assertTrue(retry.accepted)
        self.assertEqual(
            retry.operation.disposition,
            ReleaseAssuranceAttestationRegistryStoreDisposition.IDEMPOTENT,
        )
        self.assertEqual(retry.store.registry.entry_count, 2)
        self.assertEqual(retry.store.idempotent_count, 1)
        self.assertTrue(audit_release_assurance_attestation_registry_store(retry.store).accepted)

    def test_duplicate_head_and_capacity_policies_are_fail_closed(self) -> None:
        store = self._store()
        duplicate = append_release_assurance_attestation_registry_store(store, self.same_id)
        self.assertFalse(duplicate.accepted)
        self.assertEqual(
            duplicate.operation.disposition,
            ReleaseAssuranceAttestationRegistryStoreDisposition.REJECTED,
        )
        self.assertEqual(duplicate.store.registry.entry_count, 1)
        stale = append_release_assurance_attestation_registry_store(
            store,
            self.second,
            expected_head_address="wrong-head",
        )
        self.assertFalse(stale.accepted)
        self.assertEqual(stale.store.rejection_count, 1)
        tiny = build_release_assurance_attestation_registry_store(
            store.registry,
            store_id="tiny-store",
            policy=build_release_assurance_attestation_registry_store_policy(
                store.registry.registry_id,
                max_entries=1,
                max_operations=8,
            ),
        )
        capacity = append_release_assurance_attestation_registry_store(tiny, self.second)
        self.assertFalse(capacity.accepted)
        self.assertEqual(capacity.store.registry.entry_count, 1)

    def test_batch_query_replay_and_diff_are_deterministic(self) -> None:
        store = self._store()
        batch = append_release_assurance_attestation_registry_store_batch(
            store,
            [self.second, self.first],
            expected_head_address=store.head_address,
        )
        self.assertTrue(batch.accepted)
        self.assertEqual(batch.appended_count, 1)
        self.assertEqual(batch.idempotent_count, 1)
        self.assertEqual(batch.rejected_count, 0)
        self.assertEqual(batch.store.registry.entry_count, 2)
        query = query_release_assurance_attestation_registry_store_operations(
            batch.store,
            disposition="appended",
            limit=1,
        )
        self.assertEqual(query["total"], 1)
        self.assertTrue(query["accepted"])
        replay = replay_release_assurance_attestation_registry_store(
            batch.store,
            [self.first, self.second],
        )
        self.assertTrue(replay.deterministic)
        self.assertTrue(replay.accepted)
        diff = diff_release_assurance_attestation_registry_stores(store, batch.store)
        self.assertFalse(diff["identical"])
        self.assertEqual(len(diff["added_operation_ids"]), 2)

    def test_strict_contract_rejects_wrong_operation_state(self) -> None:
        store = self._store()
        payload = store.to_dict()
        payload["operations"] = [
            {
                "ordinal": 1,
                "operation_id": "operation:000001:append:bad",
                "kind": "append",
                "disposition": "rejected",
                "state": "accepted",
                "anomaly_code": "none",
                "attestation_id": None,
                "attestation_address": None,
                "before_address": store.registry.content_address,
                "after_address": store.registry.content_address,
                "entry_id": None,
                "changed_summary_fields": [],
                "audit_check_ids": [],
                "accepted": False,
                "content_address": "invalid",
            }
        ]
        payload["operation_count"] = 1
        payload["rejection_count"] = 1
        payload["content_address"] = "invalid"
        with self.assertRaises(ValidationError):
            verify_release_assurance_attestation_registry_store(payload)
        self.assertEqual(ReleaseAssuranceAttestationRegistryStoreState.ACCEPTED.value, "accepted")

    def test_api_and_cli_store_surfaces(self) -> None:
        server = create_server("127.0.0.1", 0, ".")
        server.glio_release_assurance_attestations = {
            ("registry-store-api-bundle", "registry-store-api-run"): self.first
        }
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = server.server_address
            connection = HTTPConnection(host, port, timeout=30)
            connection.request(
                "GET",
                "/v1/release-assurance/attestation/registry/store"
                "?bundle_id=registry-store-api-bundle&run_id=registry-store-api-run",
            )
            response = connection.getresponse()
            store_payload = json.loads(response.read())
            self.assertEqual(response.status, 200)
            self.assertTrue(store_payload["accepted"])

            verify_body = json.dumps({"store": store_payload}).encode("utf-8")
            connection.request(
                "POST",
                "/v1/release-assurance/attestation/registry/store/verify",
                verify_body,
                {"Content-Type": "application/json"},
            )
            response = connection.getresponse()
            verification = json.loads(response.read())
            self.assertEqual(response.status, 200)
            self.assertTrue(verification["accepted"])

            append_body = json.dumps(
                {"store": store_payload, "attestation": self.second.to_dict()}
            ).encode("utf-8")
            connection.request(
                "POST",
                "/v1/release-assurance/attestation/registry/store/append",
                append_body,
                {"Content-Type": "application/json"},
            )
            response = connection.getresponse()
            append_payload = json.loads(response.read())
            self.assertEqual(response.status, 200)
            self.assertTrue(append_payload["accepted"])
            self.assertEqual(append_payload["store"]["registry"]["entry_count"], 2)

            query_body = json.dumps(
                {
                    "store": append_payload["store"],
                    "query": {"disposition": "appended", "limit": 2},
                }
            ).encode("utf-8")
            connection.request(
                "POST",
                "/v1/release-assurance/attestation/registry/store/query",
                query_body,
                {"Content-Type": "application/json"},
            )
            response = connection.getresponse()
            query_payload = json.loads(response.read())
            self.assertEqual(response.status, 200)
            self.assertEqual(query_payload["total"], 1)
        finally:
            server.shutdown()
            server.server_close()

        with tempfile.TemporaryDirectory() as directory:
            output = str(Path(directory) / "store.json")
            self.assertEqual(
                main(
                    [
                        "release-assurance-attestation",
                        "--plane",
                        "registry-store-append",
                        "--registry-id",
                        "registry-cli-test",
                        "--store-id",
                        "registry-cli-store",
                        "--output",
                        output,
                    ]
                ),
                0,
            )
            cli_payload = json.loads(Path(output).read_text(encoding="utf-8"))
            self.assertTrue(cli_payload["accepted"])
            self.assertEqual(cli_payload["store"]["registry"]["entry_count"], 2)


if __name__ == "__main__":
    unittest.main()
