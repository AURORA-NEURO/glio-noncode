"""Adversarial tests for canonical model hydration and dossier graph closure."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from dataclasses import replace

from glio_noncode.errors import ValidationError
from glio_noncode.models import (
    CaseManifest,
    Dossier,
    ReferenceContext,
    ReviewDecision,
    ReviewState,
)
from glio_noncode.replay import ReplayVerifier
from glio_noncode.run_catalog import inspect_run
from glio_noncode.runtime import CaseRuntime
from glio_noncode.serialization import content_hash
from glio_noncode.validation import ContractValidator

from .helpers import fixture_manifest


def _readdress_dossier(raw: dict[str, object]) -> dict[str, object]:
    body = {key: value for key, value in raw.items() if key != "content_address"}
    raw["content_address"] = content_hash(body)
    return raw


class CoreModelIntegrityTests(unittest.TestCase):
    def _persisted_fixture(self) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        runtime = CaseRuntime(directory.name)
        dossier = runtime.evaluate(fixture_manifest())
        run = runtime.get_run(dossier.run_id)
        events = runtime.store.store.get(run["event_address"])
        stored = runtime.store.store.get(run["dossier_address"])
        self.assertIsInstance(events, dict)
        self.assertIsInstance(stored, dict)
        return run, events, stored

    def test_generated_v1_dossier_round_trips_without_identity_change(self) -> None:
        _, _, raw = self._persisted_fixture()
        dossier = Dossier.from_dict(raw)

        self.assertEqual(dossier.to_dict(), raw)
        self.assertEqual(dossier.content_address, raw["content_address"])

    def test_direct_required_string_misuse_is_a_typed_validation_error(self) -> None:
        with self.assertRaisesRegex(ValidationError, "genome_build must be a string"):
            ReferenceContext(
                genome_build=7,  # type: ignore[arg-type]
                disease_class="diffuse_glioma",
                age_group="adult",
                cell_state="stem_like",
            )

        raw = fixture_manifest().to_dict()
        raw["candidate_elements"][0]["context"] = None
        with self.assertRaisesRegex(ValidationError, "context must be an object"):
            CaseManifest.from_dict(raw)

    def test_identity_maps_are_recursively_copied_and_immutable(self) -> None:
        manifest_raw = fixture_manifest().to_dict()
        manifest = fixture_manifest().from_dict(manifest_raw)
        address = manifest.content_address
        metadata = manifest_raw["metadata"]
        self.assertIsInstance(metadata, dict)
        metadata["purpose"] = "caller mutation"

        self.assertEqual(manifest.content_address, address)
        self.assertIsInstance(manifest.metadata, dict)
        self.assertEqual(
            json.loads(json.dumps(manifest.metadata))["purpose"],
            "local integration fixture",
        )
        with self.assertRaises(TypeError):
            manifest.metadata["purpose"] = "object mutation"  # type: ignore[index]

        _, _, dossier_raw = self._persisted_fixture()
        dossier = Dossier.from_dict(dossier_raw)
        context_match = dossier.evidence[0].payload["context_match"]
        self.assertIsInstance(context_match, dict)
        with self.assertRaises(TypeError):
            context_match["score"] = 0.0  # type: ignore[index]
        matched = context_match["matched_dimensions"]  # type: ignore[index]
        self.assertIsInstance(matched, list)
        with self.assertRaises(TypeError):
            matched.append("mutation")  # type: ignore[union-attr]

    def test_empty_coercive_and_unknown_dossiers_fail_as_validation_errors(self) -> None:
        with self.assertRaises(ValidationError):
            Dossier.from_dict({})

        _, _, original = self._persisted_fixture()
        for mutate in (
            lambda raw: raw.update(research_use_only="false"),
            lambda raw: raw.update(signed_extension="silently dropped before hardening"),
            lambda raw: raw["evidence"][0].pop("created_at"),  # type: ignore[index,union-attr]
        ):
            raw = copy.deepcopy(original)
            mutate(raw)
            _readdress_dossier(raw)
            with self.subTest(mutation=mutate):
                with self.assertRaises(ValidationError):
                    Dossier.from_dict(raw)

    def test_readdressed_claim_edge_review_and_experiment_forgery_is_rejected(self) -> None:
        _, _, original = self._persisted_fixture()

        wrong_edge = copy.deepcopy(original)
        hypotheses = wrong_edge["hypotheses"]
        evidence = wrong_edge["evidence"]
        self.assertIsInstance(hypotheses, list)
        self.assertIsInstance(evidence, list)
        evidence[0]["edge_id"] = hypotheses[0]["edges"][1]["edge_id"]
        _readdress_dossier(wrong_edge)
        with self.assertRaisesRegex(ValidationError, "bound to"):
            Dossier.from_dict(wrong_edge)

        unknown_experiment_edge = copy.deepcopy(original)
        experiments = unknown_experiment_edge["experiments"]
        self.assertIsInstance(experiments, list)
        experiments[0]["tests_edges"] = ["edge-does-not-exist"]
        _readdress_dossier(unknown_experiment_edge)
        with self.assertRaisesRegex(ValidationError, "unknown edges"):
            Dossier.from_dict(unknown_experiment_edge)

        reviewed = Dossier.from_dict(original)
        review = ReviewDecision(
            review_id="review-forged-case",
            case_id="another-case",
            reviewer="reviewer",
            state=ReviewState.ACCEPTED,
            reviewed_hypothesis_ids=(reviewed.hypotheses[0].hypothesis_id,),
            rationale="A syntactically valid review attached to the wrong case.",
            checked_claim_ids=(reviewed.evidence[0].evidence_id,),
        )
        forged = replace(reviewed, review=review)
        raw = forged.to_dict()
        _readdress_dossier(raw)
        with self.assertRaisesRegex(ValidationError, "case_id"):
            Dossier.from_dict(raw)

    def test_identical_shared_edges_are_valid_but_conflicting_definitions_fail(self) -> None:
        _, _, original = self._persisted_fixture()
        shared = copy.deepcopy(original)
        hypotheses = shared["hypotheses"]
        self.assertIsInstance(hypotheses, list)
        repeated = copy.deepcopy(hypotheses[0])
        repeated["hypothesis_id"] = "hyp-shared-edge-second"
        hypotheses.append(repeated)
        _readdress_dossier(shared)

        dossier = Dossier.from_dict(shared)
        self.assertEqual(len(dossier.hypotheses), 2)
        self.assertEqual(dossier.hypotheses[0].edges[0], dossier.hypotheses[1].edges[0])

        conflicting = copy.deepcopy(shared)
        conflicting_hypotheses = conflicting["hypotheses"]
        self.assertIsInstance(conflicting_hypotheses, list)
        conflicting_hypotheses[1]["edges"][0]["target_id"] = "conflicting-target"
        _readdress_dossier(conflicting)
        with self.assertRaisesRegex(ValidationError, "conflicting definitions"):
            Dossier.from_dict(conflicting)

    def test_numeric_timestamp_and_address_boundaries_reject_readdressed_values(self) -> None:
        _, _, original = self._persisted_fixture()
        mutations = {
            "numeric overflow": lambda raw: raw["hypotheses"][0].update(  # type: ignore[index,union-attr]
                support=10**400
            ),
            "dossier timestamp": lambda raw: raw.update(created_at="not-a-timestamp"),
            "evidence timestamp": lambda raw: raw["evidence"][0].update(  # type: ignore[index,union-attr]
                created_at="2026-09-02T12:00:00+01:00"
            ),
            "event head": lambda raw: raw.update(event_head="genesis"),
            "source bundle": lambda raw: raw.update(
                source_bundle_addresses=["source:" + "a" * 64]
            ),
        }
        for label, mutate in mutations.items():
            raw = copy.deepcopy(original)
            mutate(raw)
            _readdress_dossier(raw)
            with self.subTest(label=label):
                with self.assertRaises(ValidationError):
                    Dossier.from_dict(raw)

        dossier = Dossier.from_dict(original)
        review = ReviewDecision(
            review_id="review-timestamp-check",
            case_id=dossier.case_id,
            reviewer="reviewer",
            state=ReviewState.ACCEPTED,
            reviewed_hypothesis_ids=(dossier.hypotheses[0].hypothesis_id,),
            rationale="Timestamp integrity check.",
            checked_claim_ids=(dossier.evidence[0].evidence_id,),
        )
        reviewed = replace(dossier, review=review).to_dict()
        reviewed["review"]["created_at"] = "yesterday"
        _readdress_dossier(reviewed)
        with self.assertRaisesRegex(ValidationError, "UTC timestamp"):
            Dossier.from_dict(reviewed)

    def test_evidence_causality_and_hypothesis_classifications_are_closed(self) -> None:
        _, _, original = self._persisted_fixture()

        external_dependency = copy.deepcopy(original)
        external_dependency["evidence"][0]["depends_on"] = ["source:" + "a" * 64]
        _readdress_dossier(external_dependency)
        self.assertEqual(
            Dossier.from_dict(external_dependency).evidence[0].depends_on,
            ("source:" + "a" * 64,),
        )

        mutations = {
            "dangling dependency": lambda raw: raw["evidence"][0].update(  # type: ignore[index,union-attr]
                depends_on=["missing-claim"]
            ),
            "forward dependency": lambda raw: raw["evidence"][0].update(  # type: ignore[index,union-attr]
                depends_on=[raw["evidence"][-1]["evidence_id"]]  # type: ignore[index]
            ),
            "dangling supersedes": lambda raw: raw["evidence"][-1].update(  # type: ignore[index,union-attr]
                supersedes="missing-claim"
            ),
            "wrong missing class": lambda raw: raw["hypotheses"][0].update(  # type: ignore[index,union-attr]
                missing_evidence=[raw["evidence"][0]["evidence_id"]]  # type: ignore[index]
            ),
            "dangling negative": lambda raw: raw["hypotheses"][0].update(  # type: ignore[index,union-attr]
                negative_evidence=["missing-claim"]
            ),
        }
        for label, mutate in mutations.items():
            raw = copy.deepcopy(original)
            mutate(raw)
            _readdress_dossier(raw)
            with self.subTest(label=label):
                with self.assertRaises(ValidationError):
                    Dossier.from_dict(raw)

    def test_hypothesis_named_identity_requires_a_typed_edge_path(self) -> None:
        _, _, original = self._persisted_fixture()
        forged = copy.deepcopy(original)
        hypothesis = forged["hypotheses"][0]
        variant_edge = next(
            edge for edge in hypothesis["edges"] if edge["edge_type"] == "variant_to_element"
        )
        variant_edge["target_id"] = "another-element"
        _readdress_dossier(forged)
        with self.assertRaisesRegex(ValidationError, "variant-to-element"):
            Dossier.from_dict(forged)

        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        manifest = replace(fixture_manifest(), candidate_elements=())
        abstained = CaseRuntime(directory.name).evaluate(manifest)
        self.assertEqual(
            Dossier.from_dict(abstained.to_dict()).content_address,
            abstained.content_address,
        )

    def test_validator_defends_direct_objects_with_cross_edge_claims(self) -> None:
        _, _, raw = self._persisted_fixture()
        dossier = Dossier.from_dict(raw)
        hypothesis = dossier.hypotheses[0]
        first_edge, second_edge = hypothesis.edges[:2]
        wrong_claim = next(
            claim for claim in dossier.evidence if claim.evidence_id in second_edge.claim_ids
        )
        forged_edge = replace(
            first_edge,
            claim_ids=first_edge.claim_ids + (wrong_claim.evidence_id,),
        )
        forged_hypothesis = replace(
            hypothesis,
            edges=(forged_edge,) + hypothesis.edges[1:],
        )
        forged = replace(
            dossier,
            hypotheses=(forged_hypothesis,) + dossier.hypotheses[1:],
        )

        report = ContractValidator().validate_dossier(forged)
        self.assertFalse(report.valid)
        self.assertIn("claim_edge_mismatch", {issue.code for issue in report.issues})

    def test_replay_and_catalog_fail_closed_on_a_readdressed_type_forgery(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        runtime = CaseRuntime(directory.name)
        dossier = runtime.evaluate(fixture_manifest())
        run = runtime.get_run(dossier.run_id)
        events = runtime.store.store.get(run["event_address"])
        raw = runtime.store.store.get(run["dossier_address"])
        raw["research_use_only"] = "false"
        _readdress_dossier(raw)

        report = ReplayVerifier().verify(run, events, raw)
        self.assertFalse(report.stored_dossier_matches_address)
        self.assertTrue(any("contract validation failed" in item for item in report.warnings))

        forged_address = raw["content_address"]
        runtime.store.store.put_at(forged_address, raw)
        runtime.store.save_run(
            dossier.run_id,
            input_address=run["input_address"],
            event_address=run["event_address"],
            dossier_address=forged_address,
        )
        inspection = inspect_run(runtime, dossier.run_id)
        self.assertFalse(inspection.accepted)
        self.assertFalse(inspection.summary.research_use_only)
        self.assertEqual(inspection.summary.status, "invalid")


if __name__ == "__main__":
    unittest.main()
