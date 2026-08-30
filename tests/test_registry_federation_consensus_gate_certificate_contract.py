"""Contract inventory tests for the certificate public surface."""

# ruff: noqa: E501, I001

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode import registry_federation_consensus_gate_certificate as certificate_model
from glio_noncode import registry_federation_consensus_gate_certificate_audit as certificate_audit_model
from glio_noncode import registry_federation_consensus_gate_certificate_diff as diff_model
from glio_noncode import registry_federation_consensus_gate_certificate_diff_audit as diff_audit_model
from glio_noncode import registry_federation_consensus_gate_certificate_history as history_model
from glio_noncode import registry_federation_consensus_gate_certificate_history_audit as history_audit_model
from glio_noncode import registry_federation_consensus_gate_certificate_package as package_model
from glio_noncode import registry_federation_consensus_gate_certificate_package_audit as package_audit_model
from glio_noncode import registry_federation_consensus_gate_certificate_query as query_model
from glio_noncode import registry_federation_consensus_gate_certificate_query_audit as query_audit_model
from glio_noncode import registry_federation_consensus_gate_certificate_runtime as runtime_model
from glio_noncode.public_surface_audit import PUBLIC_SURFACE_EXPECTED_COUNT, build_default_public_surface_audit
from tests.test_registry_federation_consensus_gate_certificate import CertificateFixture


class CertificateContractTests(CertificateFixture):
    def test_public_surface_inventory_includes_every_certificate_surface(self):
        value = build_default_public_surface_audit()
        self.assertTrue(value.accepted)
        self.assertEqual(value.surface_count, PUBLIC_SURFACE_EXPECTED_COUNT)
        expected = {
            "registry-federation-consensus-gate-certificate-policy-schema",
            "registry-federation-consensus-gate-certificate-check-schema",
            "registry-federation-consensus-gate-certificate-schema",
            "registry-federation-consensus-gate-certificate-capabilities",
            "registry-federation-consensus-gate-certificate-audit-check-schema",
            "registry-federation-consensus-gate-certificate-audit-schema",
            "registry-federation-consensus-gate-certificate-audit-capabilities",
            "registry-federation-consensus-gate-certificate-query-schema",
            "registry-federation-consensus-gate-certificate-query-row-schema",
            "registry-federation-consensus-gate-certificate-query-result-schema",
            "registry-federation-consensus-gate-certificate-query-capabilities",
            "registry-federation-consensus-gate-certificate-query-audit-check-schema",
            "registry-federation-consensus-gate-certificate-query-audit-schema",
            "registry-federation-consensus-gate-certificate-query-audit-capabilities",
            "registry-federation-consensus-gate-certificate-package-manifest-schema",
            "registry-federation-consensus-gate-certificate-package-schema",
            "registry-federation-consensus-gate-certificate-package-capabilities",
            "registry-federation-consensus-gate-certificate-package-audit-check-schema",
            "registry-federation-consensus-gate-certificate-package-audit-schema",
            "registry-federation-consensus-gate-certificate-package-audit-capabilities",
            "registry-federation-consensus-gate-certificate-runtime-schema",
            "registry-federation-consensus-gate-certificate-runtime-capabilities",
            "registry-federation-consensus-gate-certificate-diff-item-schema",
            "registry-federation-consensus-gate-certificate-diff-schema",
            "registry-federation-consensus-gate-certificate-diff-capabilities",
            "registry-federation-consensus-gate-certificate-diff-audit-check-schema",
            "registry-federation-consensus-gate-certificate-diff-audit-schema",
            "registry-federation-consensus-gate-certificate-diff-audit-capabilities",
            "registry-federation-consensus-gate-certificate-history-manifest-schema",
            "registry-federation-consensus-gate-certificate-history-entry-schema",
            "registry-federation-consensus-gate-certificate-history-schema",
            "registry-federation-consensus-gate-certificate-history-capabilities",
            "registry-federation-consensus-gate-certificate-history-audit-check-schema",
            "registry-federation-consensus-gate-certificate-history-audit-schema",
            "registry-federation-consensus-gate-certificate-history-audit-capabilities",
        }
        self.assertTrue(expected.issubset({item.surface_id for item in value.checks}))

    def test_all_certificate_schemas_are_closed_objects(self):
        schemas = {
            "policy": certificate_model.policy_schema(),
            "check": certificate_model.check_schema(),
            "certificate": certificate_model.certificate_schema(),
            "audit-check": certificate_audit_model.check_schema(),
            "audit": certificate_audit_model.audit_schema(),
            "query": query_model.query_schema(),
            "query-row": query_model.row_schema(),
            "query-result": query_model.result_schema(),
            "query-audit-check": query_audit_model.check_schema(),
            "query-audit": query_audit_model.audit_schema(),
            "package-manifest": package_model.manifest_schema(),
            "package": package_model.package_schema(),
            "package-audit-check": package_audit_model.check_schema(),
            "package-audit": package_audit_model.audit_schema(),
            "runtime": runtime_model.runtime_schema(),
            "diff-item": diff_model.item_schema(),
            "diff": diff_model.diff_schema(),
            "diff-audit-check": diff_audit_model.check_schema(),
            "diff-audit": diff_audit_model.audit_schema(),
            "history-manifest": history_model.manifest_schema(),
            "history-entry": history_model.entry_schema(),
            "history": history_model.history_schema(),
            "history-audit-check": history_audit_model.check_schema(),
            "history-audit": history_audit_model.audit_schema(),
        }
        for name, schema in schemas.items():
            with self.subTest(name=name):
                self.assertEqual(schema["type"], "object")
                self.assertFalse(schema["additionalProperties"])
                self.assertEqual(set(schema["required"]), set(schema["properties"]))
                json.dumps(schema)

    def test_capability_descriptors_have_bounded_feature_contracts(self):
        descriptors = (
            certificate_model.capabilities(),
            certificate_audit_model.capabilities(),
            query_model.capabilities(),
            package_model.capabilities(),
            package_audit_model.capabilities(),
            runtime_model.capabilities(),
            diff_model.capabilities(),
            diff_audit_model.capabilities(),
            query_audit_model.capabilities(),
            history_model.capabilities(),
            history_audit_model.capabilities(),
        )
        for descriptor in descriptors:
            self.assertTrue(descriptor["version"])
            self.assertTrue(descriptor["boundary"])
            self.assertTrue(descriptor["features"])
            self.assertTrue(descriptor["schemas"])
            self.assertTrue(all(isinstance(item, str) and item for item in descriptor["features"]))

    def test_check_vocabularies_are_unique_and_bounded(self):
        vocabularies = (
            certificate_model.CHECK_IDS,
            certificate_audit_model.CHECK_IDS,
            package_audit_model.CHECK_IDS,
            diff_audit_model.CHECK_IDS,
            query_audit_model.CHECK_IDS,
            history_audit_model.CHECK_IDS,
            history_model.RegistryFederationConsensusGateCertificateHistoryEntry.FIELDS,
            diff_model.FIELDS,
        )
        for vocabulary in vocabularies:
            self.assertEqual(len(vocabulary), len(set(vocabulary)))
            self.assertTrue(all(isinstance(item, str) and item and len(item) <= 192 for item in vocabulary))

    def test_json_exports_preserve_exact_public_field_sets(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.certificate_runtime(Path(temporary), "primary", "replica")
            package = package_model.build_package(value.gate_runtime, value.certificate, gate_audit=value.gate_runtime.audit, gate_query=value.gate_runtime.query, certificate_audit=value.certificate_audit, certificate_query=value.certificate_query)
            objects = {
                "certificate": json.loads(certificate_model.certificate_json(value.certificate)),
                "certificate-audit": json.loads(certificate_audit_model.audit_json(value.certificate_audit)),
                "certificate-query": json.loads(query_model.query_json(value.certificate_query)),
                "package": json.loads(package_model.package_json(package)),
                "runtime": json.loads(runtime_model.runtime_json(value)),
            }
            expected = {
                "certificate": set(certificate_model.RegistryFederationConsensusGateCertificate.FIELDS),
                "certificate-audit": set(certificate_audit_model.RegistryFederationConsensusGateCertificateAudit.FIELDS),
                "certificate-query": set(query_model.RegistryFederationConsensusGateCertificateQueryResult.FIELDS),
                "package": set(package_model.RegistryFederationConsensusGateCertificatePackage.FIELDS),
                "runtime": set(runtime_model.FIELDS),
            }
            for name, document in objects.items():
                with self.subTest(name=name):
                    self.assertEqual(set(document), expected[name])

    def test_real_fixture_has_stable_address_prefixes_across_every_layer(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.certificate_runtime(Path(temporary), "primary", "replica")
            package = package_model.build_package(value.gate_runtime, value.certificate, gate_audit=value.gate_runtime.audit, gate_query=value.gate_runtime.query, certificate_audit=value.certificate_audit, certificate_query=value.certificate_query)
            addresses = (
                value.certificate.policy.content_address,
                value.certificate.content_address,
                value.certificate_audit.content_address,
                value.certificate_query.content_address,
                package.content_address,
                value.content_address,
            )
            prefixes = (
                certificate_model.POLICY_PREFIX,
                certificate_model.CERTIFICATE_PREFIX,
                certificate_audit_model.AUDIT_PREFIX,
                query_model.RESULT_PREFIX,
                package_model.PACKAGE_PREFIX,
                runtime_model.RUNTIME_PREFIX,
            )
            for address, prefix in zip(addresses, prefixes):
                self.assertTrue(address.startswith(prefix + ":"))
                self.assertNotIn("/", address)
                self.assertNotIn("\\", address)

    def test_package_projection_hashes_are_stable_on_repeated_generation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = self.certificate_runtime(root / "first", "primary", "replica")
            second = self.certificate_runtime(root / "second", "primary", "replica")
            first_package = package_model.build_package(first.gate_runtime, first.certificate, gate_audit=first.gate_runtime.audit, gate_query=first.gate_runtime.query, certificate_audit=first.certificate_audit, certificate_query=first.certificate_query)
            second_package = package_model.build_package(second.gate_runtime, second.certificate, gate_audit=second.gate_runtime.audit, gate_query=second.gate_runtime.query, certificate_audit=second.certificate_audit, certificate_query=second.certificate_query)
            self.assertEqual(first.certificate.content_address, second.certificate.content_address)
            self.assertEqual(first.certificate_audit.content_address, second.certificate_audit.content_address)
            self.assertEqual(first.certificate_query.content_address, second.certificate_query.content_address)
            self.assertEqual(first_package.content_address, second_package.content_address)
            self.assertEqual(package_model.package_bytes(first_package), package_model.package_bytes(second_package))

    def test_held_certificate_has_explainable_failures_and_auditable_package(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.certificate_runtime(Path(temporary), "primary", "held")
            package = package_model.build_package(value.gate_runtime, value.certificate, gate_audit=value.gate_runtime.audit, gate_query=value.gate_runtime.query, certificate_audit=value.certificate_audit, certificate_query=value.certificate_query)
            failures = query_model.query_certificate(value.certificate, resources=("failures",), passed=False, limit=100)
            self.assertFalse(value.certificate.accepted)
            self.assertGreater(failures.returned_count, 0)
            self.assertEqual(set(row.check_id for row in failures.rows), set(value.certificate.blocking_check_ids))
            self.assertTrue(certificate_audit_model.audit_certificate(value.certificate).accepted)
            self.assertTrue(package_audit_model.audit_package(package).accepted)

    def test_minimum_page_limit_is_stable_at_single_row(self):
        with tempfile.TemporaryDirectory() as temporary:
            certificate = self.certificate_runtime(Path(temporary), "primary", "replica").certificate
            page = query_model.query_certificate(certificate, resources=("checks",), limit=1)
            self.assertEqual(page.returned_count, 1)
            self.assertTrue(page.truncated)
            self.assertEqual(page.next_offset, 1)
            while page.truncated:
                page = query_model.query_certificate(certificate, resources=("checks",), offset=page.next_offset, limit=1)
            self.assertEqual(page.next_offset, 0)
            self.assertFalse(page.truncated)

    def test_schema_routes_and_capabilities_have_no_local_path_values(self):
        values = [
            certificate_model.policy_schema(),
            certificate_model.certificate_schema(),
            certificate_audit_model.audit_schema(),
            query_model.result_schema(),
            package_model.package_schema(),
            package_audit_model.audit_schema(),
            runtime_model.runtime_schema(),
            diff_model.diff_schema(),
            diff_audit_model.audit_schema(),
            history_model.history_schema(),
            history_audit_model.audit_schema(),
            certificate_model.capabilities(),
            certificate_audit_model.capabilities(),
            query_model.capabilities(),
            package_model.capabilities(),
            package_audit_model.capabilities(),
            runtime_model.capabilities(),
            diff_model.capabilities(),
            diff_audit_model.capabilities(),
            history_model.capabilities(),
            history_audit_model.capabilities(),
        ]
        encoded = json.dumps(values, sort_keys=True)
        self.assertNotIn("C:\\Users\\", encoded)
        self.assertNotIn("/home/", encoded)


if __name__ == "__main__":
    unittest.main()
