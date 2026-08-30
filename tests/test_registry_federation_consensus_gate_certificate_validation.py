"""Negative and boundary tests for the certificate evidence spine."""

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
from glio_noncode import registry_federation_consensus_gate_certificate_package as package_model
from glio_noncode import registry_federation_consensus_gate_certificate_package_audit as package_audit_model
from glio_noncode import registry_federation_consensus_gate_certificate_query as query_model
from glio_noncode import registry_federation_consensus_gate_certificate_runtime as runtime_model
from glio_noncode.errors import ValidationError
from tests.test_registry_federation_consensus_gate_certificate import CertificateFixture


class CertificateValidationTests(CertificateFixture):
    def test_certificate_mapping_rejects_unknown_and_missing_fields(self):
        with tempfile.TemporaryDirectory() as temporary:
            certificate = self.certificate_runtime(Path(temporary), "primary", "replica").certificate
            document = certificate.to_dict()
            document["unexpected"] = True
            with self.assertRaises(ValidationError):
                certificate_model.certificate_from_mapping(document)
            document = certificate.to_dict()
            del document["accepted"]
            with self.assertRaises(ValidationError):
                certificate_model.certificate_from_mapping(document)

    def test_policy_mapping_rejects_unsupported_dispositions_and_bounds(self):
        policy = certificate_model.default_policy()
        document = policy.to_dict()
        document["allowed_gate_states"] = ["not-a-state"]
        with self.assertRaises(ValidationError):
            certificate_model.RegistryFederationConsensusGateCertificatePolicy.from_mapping(document)
        document = policy.to_dict()
        document["minimum_passed_count"] = certificate_model.MAX_CHECKS + 1
        with self.assertRaises(ValidationError):
            certificate_model.RegistryFederationConsensusGateCertificatePolicy.from_mapping(document)
        document = policy.to_dict()
        document["policy_id"] = "has whitespace"
        with self.assertRaises(ValidationError):
            certificate_model.RegistryFederationConsensusGateCertificatePolicy.from_mapping(document)

    def test_certificate_check_rejects_duplicate_evidence_and_address_tampering(self):
        with tempfile.TemporaryDirectory() as temporary:
            certificate = self.certificate_runtime(Path(temporary), "primary", "replica").certificate
            document = certificate.to_dict()
            document["checks"] = list(document["checks"])
            document["checks"][0] = dict(document["checks"][0])
            document["checks"][0]["evidence_addresses"] = list(document["checks"][0]["evidence_addresses"]) * 2
            with self.assertRaises(ValidationError):
                certificate_model.certificate_from_mapping(document)
            check = dict(certificate.checks[0].to_dict())
            check["content_address"] = certificate_model.CHECK_PREFIX + ":tampered"
            with self.assertRaises(ValidationError):
                certificate_model.RegistryFederationConsensusGateCertificateCheck.from_mapping(check)

    def test_certificate_rejects_inconsistent_acceptance_state_and_counters(self):
        with tempfile.TemporaryDirectory() as temporary:
            certificate = self.certificate_runtime(Path(temporary), "primary", "replica").certificate
            document = certificate.to_dict()
            document["accepted"] = False
            with self.assertRaises(ValidationError):
                certificate_model.certificate_from_mapping(document)
            document = certificate.to_dict()
            document["passed_count"] = 18
            with self.assertRaises(ValidationError):
                certificate_model.certificate_from_mapping(document)
            document = certificate.to_dict()
            document["blocking_check_ids"] = ["gate-accepted"]
            with self.assertRaises(ValidationError):
                certificate_model.certificate_from_mapping(document)

    def test_audit_mapping_rejects_unknown_fields_and_finding_address_tampering(self):
        with tempfile.TemporaryDirectory() as temporary:
            certificate = self.certificate_runtime(Path(temporary), "primary", "replica").certificate
            audit = certificate_audit_model.audit_certificate(certificate)
            document = audit.to_dict()
            document["unknown"] = "value"
            with self.assertRaises(ValidationError):
                certificate_audit_model.audit_from_mapping(document)
            finding = dict(audit.checks[0].to_dict())
            finding["content_address"] = certificate_audit_model.FINDING_PREFIX + ":tampered"
            with self.assertRaises(ValidationError):
                certificate_audit_model.RegistryFederationConsensusGateCertificateAuditFinding.from_mapping(finding)

    def test_query_result_rejects_nonconserved_ordinals_and_content_address(self):
        with tempfile.TemporaryDirectory() as temporary:
            certificate = self.certificate_runtime(Path(temporary), "primary", "replica").certificate
            result = query_model.query_certificate(certificate, resources=("checks",), limit=3)
            document = result.to_dict()
            document["rows"] = list(document["rows"])
            document["rows"][0] = dict(document["rows"][0])
            document["rows"][0]["ordinal"] = 2
            with self.assertRaises(ValidationError):
                query_model.query_from_mapping(document)
            document = result.to_dict()
            document["content_address"] = query_model.RESULT_PREFIX + ":tampered"
            with self.assertRaises(ValidationError):
                query_model.query_from_mapping(document)

    def test_query_rows_cannot_cross_resource_or_evidence_boundaries(self):
        with tempfile.TemporaryDirectory() as temporary:
            certificate = self.certificate_runtime(Path(temporary), "primary", "replica").certificate
            result = query_model.query_certificate(certificate, resources=("checks",), limit=1)
            row = dict(result.rows[0].to_dict())
            row["resource"] = "not-a-resource"
            with self.assertRaises(ValidationError):
                query_model.RegistryFederationConsensusGateCertificateQueryRow.from_mapping(row)
            row = dict(result.rows[0].to_dict())
            row["evidence_addresses"] = []
            with self.assertRaises(ValidationError):
                query_model.RegistryFederationConsensusGateCertificateQueryRow.from_mapping(row)
            query = dict(result.query.to_dict())
            query["resources"] = ["unknown"]
            with self.assertRaises(ValidationError):
                query_model.RegistryFederationConsensusGateCertificateQuery.from_mapping(query)

    def test_package_mapping_rejects_unknown_fields_and_nested_link_tampering(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = self.certificate_runtime(root, "primary", "replica")
            package = package_model.build_package(runtime.gate_runtime, runtime.certificate, gate_audit=runtime.gate_runtime.audit, gate_query=runtime.gate_runtime.query, certificate_audit=runtime.certificate_audit, certificate_query=runtime.certificate_query)
            document = package.to_dict()
            document["unknown"] = True
            with self.assertRaises(ValidationError):
                package_model.package_from_mapping(document)
            document = package.to_dict()
            document["certificate"] = dict(document["certificate"])
            document["certificate"]["gate_address"] = "wrong-gate-address"
            with self.assertRaises(ValidationError):
                package_model.package_from_mapping(document)
            document = package.to_dict()
            document["content_address"] = package_model.PACKAGE_PREFIX + ":tampered"
            with self.assertRaises(ValidationError):
                package_model.package_from_mapping(document)

    def test_package_audit_detects_child_address_changes(self):
        with tempfile.TemporaryDirectory() as temporary:
            runtime = self.certificate_runtime(Path(temporary), "primary", "replica")
            package = package_model.build_package(runtime.gate_runtime, runtime.certificate, gate_audit=runtime.gate_runtime.audit, gate_query=runtime.gate_runtime.query, certificate_audit=runtime.certificate_audit, certificate_query=runtime.certificate_query)
            document = package.to_dict()
            document["certificate_audit"] = dict(document["certificate_audit"])
            document["certificate_audit"]["certificate_address"] = certificate_model.CERTIFICATE_PREFIX + ":wrong"
            with self.assertRaises(ValidationError):
                package_model.package_from_mapping(document)
            audit = package_audit_model.audit_package(package)
            audit_document = audit.to_dict()
            audit_document["checks"] = list(audit_document["checks"])
            audit_document["checks"][0] = dict(audit_document["checks"][0])
            audit_document["checks"][0]["observed"] = "tampered"
            with self.assertRaises(ValidationError):
                package_audit_model.audit_from_mapping(audit_document)

    def test_diff_mapping_rejects_unknown_field_invalid_action_and_hash_tampering(self):
        with tempfile.TemporaryDirectory() as temporary:
            runtime = self.gate_runtime(Path(temporary), "primary", "replica")
            left = certificate_model.evaluate_certificate(runtime)
            right = certificate_model.evaluate_certificate(runtime, policy=self.strict_certificate_policy(minimum_passed_count=runtime.gate.check_count + 1), certificate_id="held")
            value = diff_model.build_diff(left, right)
            document = value.to_dict()
            document["unexpected"] = True
            with self.assertRaises(ValidationError):
                diff_model.diff_from_mapping(document)
            document = value.to_dict()
            document["items"] = list(document["items"])
            document["items"][0] = dict(document["items"][0])
            document["items"][0]["action"] = "invalid"
            with self.assertRaises(ValidationError):
                diff_model.diff_from_mapping(document)
            document = value.to_dict()
            document["content_address"] = diff_model.DIFF_PREFIX + ":tampered"
            with self.assertRaises(ValidationError):
                diff_model.diff_from_mapping(document)

    def test_diff_audit_rejects_counter_unknown_field_and_address_tampering(self):
        with tempfile.TemporaryDirectory() as temporary:
            runtime = self.gate_runtime(Path(temporary), "primary", "replica")
            left = certificate_model.evaluate_certificate(runtime)
            right = certificate_model.evaluate_certificate(runtime, policy=self.strict_certificate_policy(minimum_passed_count=runtime.gate.check_count + 1), certificate_id="held")
            diff = diff_model.build_diff(left, right)
            audit = diff_audit_model.audit_diff(diff)
            document = audit.to_dict()
            document["failed_count"] = 1
            with self.assertRaises(ValidationError):
                diff_audit_model.audit_from_mapping(document)
            document = audit.to_dict()
            document["unknown"] = 1
            with self.assertRaises(ValidationError):
                diff_audit_model.audit_from_mapping(document)
            finding = dict(audit.checks[0].to_dict())
            finding["content_address"] = diff_audit_model.FINDING_PREFIX + ":tampered"
            with self.assertRaises(ValidationError):
                diff_audit_model.RegistryFederationConsensusGateCertificateDiffAuditFinding.from_mapping(finding)

    def test_runtime_mapping_rejects_persistence_state_without_package(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.certificate_runtime(Path(temporary), "primary", "replica")
            document = value.to_dict()
            document["persisted"] = True
            with self.assertRaises(ValidationError):
                runtime_model.runtime_from_mapping(document)
            document = value.to_dict()
            document["package_address"] = package_model.PACKAGE_PREFIX + ":orphan"
            with self.assertRaises(ValidationError):
                runtime_model.runtime_from_mapping(document)

    def test_all_certificate_exports_are_free_of_paths_and_forbidden_metadata_keys(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = self.certificate_runtime(root, "primary", "replica")
            package = package_model.build_package(runtime.gate_runtime, runtime.certificate, gate_audit=runtime.gate_runtime.audit, gate_query=runtime.gate_runtime.query, certificate_audit=runtime.certificate_audit, certificate_query=runtime.certificate_query)
            payloads = [
                certificate_model.certificate_json(runtime.certificate),
                certificate_audit_model.audit_json(runtime.certificate_audit),
                query_model.query_json(runtime.certificate_query),
                package_model.package_json(package),
                runtime_model.runtime_json(runtime),
            ]
            for payload in payloads:
                self.assertNotIn("C:\\Users\\", payload)
                self.assertNotIn("/home/", payload)
                decoded = json.loads(payload)
                self.assertNotIn("agent", {key.lower() for key in decoded if isinstance(key, str)})


if __name__ == "__main__":
    unittest.main()
