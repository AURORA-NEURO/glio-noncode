"""Core contract tests for consensus release certificates and handoff packages."""

# ruff: noqa: E501, I001

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode import registry_federation_consensus_gate as gate_model
from glio_noncode import registry_federation_consensus_gate_certificate as certificate_model
from glio_noncode import registry_federation_consensus_gate_certificate_audit as certificate_audit_model
from glio_noncode import registry_federation_consensus_gate_certificate_diff as diff_model
from glio_noncode import registry_federation_consensus_gate_certificate_diff_audit as diff_audit_model
from glio_noncode import registry_federation_consensus_gate_certificate_package as package_model
from glio_noncode import registry_federation_consensus_gate_certificate_package_audit as package_audit_model
from glio_noncode import registry_federation_consensus_gate_certificate_query as query_model
from glio_noncode import registry_federation_consensus_gate_certificate_runtime as certificate_runtime_model
from glio_noncode import registry_federation_consensus_gate_runtime as gate_runtime_model
from glio_noncode.errors import ValidationError
from tests.test_assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package import DurableCatalogPromotionPackageFixture


class CertificateFixture(DurableCatalogPromotionPackageFixture):
    """Generate canonical downloaded-package-shaped registries for each test."""

    def registry_for(self, path: Path, package, *, registry_id: str) -> Path:
        from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package_registry as registry_model

        value = registry_model.build_registry((package,), registry_id=registry_id)
        registry_model.write_registry(value, path)
        return path

    def registries(self, root: Path) -> tuple[Path, Path, Path]:
        ready_package = self.package_for(root / "ready-input", package_id="certificate-ready")
        held_package = self.package_for(root / "held-input", package_id="certificate-held", held=True)
        ready = self.registry_for(root / "ready", ready_package, registry_id="certificate-ready-registry")
        copy = self.registry_for(root / "copy", ready_package, registry_id="certificate-copy-registry")
        held = self.registry_for(root / "held", held_package, registry_id="certificate-held-registry")
        return ready, copy, held

    def gate_runtime(self, root: Path, *names: str, destination: Path | None = None) -> gate_runtime_model.RegistryFederationConsensusGateRuntime:
        ready, copy, held = self.registries(root / "registries")
        paths = {"primary": ready, "replica": copy, "held": held}
        return gate_runtime_model.run_gate_runtime(
            tuple((name, paths[name]) for name in names),
            runtime_id="certificate-gate-runtime",
            federation_id="certificate-federation",
            consensus_id="certificate-consensus",
            gate_id="certificate-gate",
            package_id="certificate-gate-package",
            destination=destination,
            resources=("summary", "checks", "failures", "evidence"),
            limit=100,
        )

    def certificate_runtime(self, root: Path, *names: str, destination: Path | None = None) -> certificate_runtime_model.RegistryFederationConsensusGateCertificateRuntime:
        ready, copy, held = self.registries(root / "registries")
        paths = {"primary": ready, "replica": copy, "held": held}
        return certificate_runtime_model.run_certificate_runtime(
            tuple((name, paths[name]) for name in names),
            runtime_id="certificate-runtime",
            federation_id="certificate-federation",
            consensus_id="certificate-consensus",
            gate_id="certificate-gate",
            certificate_id="certificate",
            package_id="certificate-package",
            destination=destination,
            certificate_resources=("summary", "checks", "failures", "evidence", "policy"),
            limit=100,
        )

    def strict_certificate_policy(self, *, minimum_passed_count: int = 1, require_package: bool = False) -> certificate_model.RegistryFederationConsensusGateCertificatePolicy:
        pending = certificate_model.RegistryFederationConsensusGateCertificatePolicy(
            "strict-certificate-policy",
            ("eligible",),
            ("promote",),
            1,
            minimum_passed_count,
            True,
            True,
            True,
            require_package,
            certificate_model.POLICY_PREFIX + ":pending",
        )
        return certificate_model.RegistryFederationConsensusGateCertificatePolicy(
            pending.policy_id,
            pending.allowed_gate_states,
            pending.allowed_gate_decisions,
            pending.minimum_check_count,
            pending.minimum_passed_count,
            pending.require_gate_acceptance,
            pending.require_gate_audit,
            pending.require_query_complete,
            pending.require_package,
            certificate_model.address_policy(pending),
        )


class CertificateCoreTests(CertificateFixture):
    def test_clean_certificate_is_issued_with_conserved_checks(self):
        with tempfile.TemporaryDirectory() as temporary:
            runtime = self.certificate_runtime(Path(temporary), "primary", "replica")
            value = runtime.certificate
            self.assertTrue(value.accepted)
            self.assertEqual((value.certificate_state, value.certificate_decision), ("issued", "promote"))
            self.assertEqual((value.check_count, value.passed_count, value.failed_count), (19, 19, 0))
            self.assertEqual(value.runtime_address, runtime.gate_runtime.content_address)
            self.assertEqual(value.gate_address, runtime.gate_runtime.gate.content_address)
            self.assertEqual(value.audit_address, runtime.gate_runtime.audit.content_address)
            self.assertEqual(value.query_address, runtime.gate_runtime.query.content_address)
            self.assertEqual(value.blocking_check_ids, ())

    def test_divergent_downloaded_registries_withhold_certificate(self):
        with tempfile.TemporaryDirectory() as temporary:
            runtime = self.certificate_runtime(Path(temporary), "primary", "held")
            value = runtime.certificate
            self.assertFalse(value.accepted)
            self.assertEqual((value.certificate_state, value.certificate_decision), ("withheld", "hold"))
            self.assertGreater(value.failed_count, 0)
            self.assertEqual(value.failed_count, len(value.blocking_check_ids))
            self.assertIn("gate-accepted", value.blocking_check_ids)
            self.assertIn("state-allowed", value.blocking_check_ids)
            self.assertIn("decision-allowed", value.blocking_check_ids)
            self.assertTrue(runtime.certificate_audit.accepted)

    def test_default_policy_is_addressed_and_has_explicit_requirements(self):
        policy = certificate_model.default_policy(policy_id="policy-test")
        self.assertEqual(certificate_model.address_policy(policy), policy.content_address)
        self.assertEqual(policy.allowed_gate_states, ("eligible",))
        self.assertEqual(policy.allowed_gate_decisions, ("promote",))
        self.assertEqual(policy.minimum_check_count, 1)
        self.assertEqual(policy.minimum_passed_count, 1)
        self.assertTrue(policy.require_gate_acceptance)
        self.assertTrue(policy.require_gate_audit)
        self.assertTrue(policy.require_query_complete)
        self.assertFalse(policy.require_package)
        self.assertEqual(set(policy.to_dict()), set(policy.FIELDS))
        self.assertEqual(certificate_model.RegistryFederationConsensusGateCertificatePolicy.from_mapping(policy.to_dict()).to_dict(), policy.to_dict())

    def test_certificate_policy_can_withhold_without_mutating_gate_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            runtime = self.gate_runtime(Path(temporary), "primary", "replica")
            original_gate_address = runtime.gate.content_address
            policy = self.strict_certificate_policy(minimum_passed_count=runtime.gate.check_count + 1)
            value = certificate_model.evaluate_certificate(runtime, policy=policy, certificate_id="strict-certificate")
            self.assertFalse(value.accepted)
            self.assertEqual((value.certificate_state, value.certificate_decision), ("withheld", "hold"))
            self.assertIn("check-floor", value.blocking_check_ids)
            self.assertEqual(runtime.gate.content_address, original_gate_address)
            self.assertTrue(runtime.gate.accepted)

    def test_package_requirement_is_satisfied_only_by_a_persisted_gate_package(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            in_memory = self.gate_runtime(root / "memory", "primary", "replica")
            strict = certificate_model.evaluate_certificate(in_memory, policy=self.strict_certificate_policy(require_package=True))
            self.assertFalse(strict.accepted)
            self.assertIn("package-link", strict.blocking_check_ids)
            persisted = self.gate_runtime(root / "persisted", "primary", "replica", destination=root / "gate-package")
            issued = certificate_model.evaluate_certificate(persisted, policy=self.strict_certificate_policy(require_package=True))
            self.assertTrue(issued.accepted)
            self.assertTrue(issued.package_address)

    def test_certificate_serializers_are_deterministic_and_public(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.certificate_runtime(Path(temporary), "primary", "replica").certificate
            document = json.loads(certificate_model.certificate_json(value))
            self.assertEqual(certificate_model.certificate_from_mapping(document).to_dict(), value.to_dict())
            self.assertEqual(tuple(item.ordinal for item in value.checks), tuple(range(1, 20)))
            self.assertIn("# Consensus Release Certificate", certificate_model.render_certificate_markdown(value))
            csv_text = certificate_model.certificate_csv(value)
            self.assertTrue(csv_text.startswith("ordinal,check_id,passed,detail,evidence_addresses,content_address"))
            self.assertNotIn("/Users/", certificate_model.certificate_json(value))
            self.assertNotIn("\\Users\\", certificate_model.certificate_json(value))
            self.assertNotIn('"agent"', certificate_model.certificate_json(value))

    def test_audit_recomputes_certificate_and_round_trips(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.certificate_runtime(Path(temporary), "primary", "replica").certificate
            audit = certificate_audit_model.audit_certificate(value)
            self.assertTrue(audit.accepted)
            self.assertEqual((audit.check_count, audit.passed_count, audit.failed_count), (20, 20, 0))
            self.assertEqual(audit.certificate_address, value.content_address)
            self.assertEqual(certificate_audit_model.audit_from_mapping(audit.to_dict()).to_dict(), audit.to_dict())
            self.assertIn("independent certificate structure checks", certificate_audit_model.capabilities()["features"])

    def test_audit_rejects_counter_and_address_tampering(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.certificate_runtime(Path(temporary), "primary", "replica").certificate
            audit = certificate_audit_model.audit_certificate(value)
            corrupted = audit.to_dict()
            corrupted["passed_count"] = 0
            with self.assertRaises(ValidationError):
                certificate_audit_model.audit_from_mapping(corrupted)
            corrupted = audit.to_dict()
            corrupted["checks"] = list(corrupted["checks"])
            corrupted["checks"][0] = dict(corrupted["checks"][0])
            corrupted["checks"][0]["detail"] = "changed"
            with self.assertRaises(ValidationError):
                certificate_audit_model.audit_from_mapping(corrupted)
            corrupted = audit.to_dict()
            corrupted["content_address"] = certificate_audit_model.AUDIT_PREFIX + ":tampered"
            with self.assertRaises(ValidationError):
                certificate_audit_model.audit_from_mapping(corrupted)

    def test_certificate_runtime_replays_all_nested_members(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.certificate_runtime(Path(temporary), "primary", "replica")
            self.assertFalse(value.persisted)
            self.assertEqual(value.package_address, "")
            self.assertEqual(value.certificate.runtime_address, value.gate_runtime.content_address)
            self.assertEqual(value.certificate_audit.certificate_address, value.certificate.content_address)
            self.assertEqual(value.certificate_query.query.certificate_address, value.certificate.content_address)
            self.assertEqual(certificate_runtime_model.runtime_from_mapping(value.to_dict()).to_dict(), value.to_dict())
            self.assertEqual(json.loads(certificate_runtime_model.runtime_json(value))["certificate"]["accepted"], True)

    def test_certificate_runtime_can_persist_the_certificate_package(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            value = self.certificate_runtime(root, "primary", "replica", destination=root / "certificate-package")
            self.assertTrue(value.persisted)
            self.assertTrue(value.package_address.startswith(package_model.PACKAGE_PREFIX + ":"))
            loaded = package_model.load_package(root / "certificate-package")
            self.assertEqual(loaded.content_address, value.package_address)


if __name__ == "__main__":
    unittest.main()
