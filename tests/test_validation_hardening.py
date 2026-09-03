"""Adversarial tests for the bounded dossier validation and release boundary."""

from __future__ import annotations

import copy
import tempfile
import unittest
from dataclasses import replace
from unittest.mock import patch

import glio_noncode.validation as validation_module
from glio_noncode.data_sources import FetchReceipt, FetchStatus
from glio_noncode.errors import ValidationError
from glio_noncode.models import (
    Dossier,
    ResearchStatus,
    ReviewDecision,
    ReviewState,
)
from glio_noncode.runtime import CaseRuntime
from glio_noncode.serialization import content_hash
from glio_noncode.validation import (
    ContractValidator,
    ReleaseGate,
    ValidationLimits,
)

from .helpers import fixture_manifest


def _readdress(dossier: Dossier) -> Dossier:
    pending = replace(dossier, content_address="pending")
    body = pending.to_dict()
    body.pop("content_address")
    return replace(pending, content_address=content_hash(body))


class ValidationHardeningTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.runtime = CaseRuntime(self.directory.name)
        self.draft = self.runtime.evaluate(fixture_manifest())
        review = ReviewDecision(
            review_id="validation-hardening-review",
            case_id=self.draft.case_id,
            reviewer="scientific-reviewer",
            state=ReviewState.ACCEPTED,
            reviewed_hypothesis_ids=tuple(
                hypothesis.hypothesis_id for hypothesis in self.draft.hypotheses
            ),
            rationale="Every hypothesis and evidence claim was checked for this snapshot.",
            checked_claim_ids=tuple(claim.evidence_id for claim in self.draft.evidence),
        )
        self.released = self.runtime.review(self.draft, review)

    def test_generated_manifest_draft_and_release_remain_structurally_valid(self) -> None:
        validator = ContractValidator()

        self.assertTrue(validator.validate_manifest(fixture_manifest()).valid)
        self.assertTrue(validator.validate_dossier(self.draft).valid)
        self.assertTrue(validator.validate_dossier(self.released).valid)
        self.assertTrue(ReleaseGate().check(self.released).valid)

    def test_exact_top_level_and_nested_types_fail_closed_without_crashing(self) -> None:
        validator = ContractValidator()

        self.assertEqual(
            validator.validate_manifest(object()).issues[0].code,  # type: ignore[arg-type]
            "invalid_manifest_type",
        )
        self.assertEqual(
            validator.validate_dossier(object()).issues[0].code,  # type: ignore[arg-type]
            "invalid_dossier_type",
        )

        forged_dossier = copy.copy(self.draft)
        object.__setattr__(forged_dossier, "evidence", list(self.draft.evidence))
        report = validator.validate_dossier(forged_dossier)
        self.assertFalse(report.valid)
        self.assertEqual({issue.code for issue in report.issues}, {"noncanonical_object_graph"})

        forged_manifest = copy.copy(fixture_manifest())
        object.__setattr__(forged_manifest, "variants", (object(),))
        report = validator.validate_manifest(forged_manifest)
        self.assertFalse(report.valid)
        self.assertEqual({issue.code for issue in report.issues}, {"noncanonical_object_graph"})

    def test_limits_are_downward_only_and_mutation_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValidationError, "must be an integer"):
            ValidationLimits(max_evidence_claims=True)  # type: ignore[arg-type]
        with patch.object(validation_module, "MAX_VALIDATION_EVIDENCE_CLAIMS", 1_000_000):
            with self.assertRaisesRegex(ValidationError, "safety ceiling"):
                ValidationLimits(max_evidence_claims=20_001)

        validator = ContractValidator(
            limits=ValidationLimits(max_evidence_claims=len(self.draft.evidence) - 1)
        )
        report = validator.validate_dossier(self.draft)
        self.assertFalse(report.valid)
        self.assertEqual(report.issues[0].code, "validation_limit_exceeded")

        validator = ContractValidator()
        object.__setattr__(validator.limits, "max_evidence_claims", 20_001)
        report = validator.validate_dossier(self.draft)
        self.assertFalse(report.valid)
        self.assertEqual(report.issues[0].code, "invalid_validation_limits")

    def test_external_dependencies_must_close_over_retained_addresses(self) -> None:
        external = content_hash({"external": "source-response"})
        changed_claim = replace(self.draft.evidence[0], depends_on=(external,))
        changed = _readdress(
            replace(
                self.draft,
                evidence=(changed_claim,) + self.draft.evidence[1:],
            )
        )

        report = ContractValidator().validate_dossier(changed)
        self.assertFalse(report.valid)
        self.assertIn("undeclared_evidence_dependency", {item.code for item in report.issues})

        declared = _readdress(replace(changed, source_bundle_addresses=(external,)))
        report = ContractValidator().validate_dossier(declared)
        self.assertNotIn("undeclared_evidence_dependency", {item.code for item in report.issues})

    def test_source_receipts_are_exact_and_close_response_dependencies(self) -> None:
        request_hash = content_hash({"request": "validation"})
        response_hash = content_hash({"response": "validation"})
        receipt = FetchReceipt(
            source_id="SRC-ENSEMBL-REST",
            source_version="fixture-1",
            url="https://ensembl.example/overlap",
            request_hash=request_hash,
            response_hash=response_hash,
            status=FetchStatus.FETCHED,
            http_status=200,
            attempts=1,
            retrieved_at="2026-09-02T00:00:00+00:00",
            elapsed_seconds=0.01,
            cache_expires_at=None,
        )
        changed_claim = replace(self.draft.evidence[0], depends_on=(response_hash,))
        dossier = _readdress(
            replace(
                self.draft,
                evidence=(changed_claim,) + self.draft.evidence[1:],
                source_receipts=(receipt.to_dict(),),
                source_bundle_addresses=(content_hash({"bundle": "validation"}),),
            )
        )
        report = ContractValidator().validate_dossier(dossier)
        self.assertNotIn("invalid_source_receipt", {item.code for item in report.issues})
        self.assertNotIn("undeclared_evidence_dependency", {item.code for item in report.issues})

        malformed = receipt.to_dict()
        malformed["attempts"] = 0
        forged = _readdress(replace(dossier, source_receipts=(malformed,)))
        report = ContractValidator().validate_dossier(forged)
        self.assertFalse(report.valid)
        self.assertIn("invalid_source_receipt", {item.code for item in report.issues})

    def test_supersession_must_remain_on_the_same_edge(self) -> None:
        first = self.draft.evidence[0]
        later_index = next(
            index
            for index, claim in enumerate(self.draft.evidence[1:], start=1)
            if claim.edge_id != first.edge_id
        )
        later = replace(self.draft.evidence[later_index], supersedes=first.evidence_id)
        evidence = list(self.draft.evidence)
        evidence[later_index] = later
        forged = _readdress(replace(self.draft, evidence=tuple(evidence)))

        report = ContractValidator().validate_dossier(forged)

        self.assertFalse(report.valid)
        self.assertIn("cross_edge_evidence_supersession", {item.code for item in report.issues})

    def test_accepted_release_review_must_exhaust_hypotheses_and_claims(self) -> None:
        assert self.released.review is not None
        second_hypothesis = replace(
            self.released.hypotheses[0],
            hypothesis_id="hyp-validation-review-coverage",
        )
        incomplete_review = replace(
            self.released.review,
            checked_claim_ids=(self.released.evidence[0].evidence_id,),
        )
        forged = _readdress(
            replace(
                self.released,
                hypotheses=self.released.hypotheses + (second_hypothesis,),
                review=incomplete_review,
            )
        )

        report = ContractValidator().validate_dossier(forged)
        codes = {item.code for item in report.issues}

        self.assertFalse(report.valid)
        self.assertIn("incomplete_hypothesis_review", codes)
        self.assertIn("incomplete_claim_review", codes)

    def test_release_gate_rejects_every_nonrelease_status_with_forged_policy(self) -> None:
        for status in (
            ResearchStatus.DRAFT,
            ResearchStatus.REVIEW_REQUIRED,
            ResearchStatus.REVIEWED,
            ResearchStatus.SUPERSEDED,
        ):
            dossier = _readdress(replace(self.draft, status=status))
            gate = ReleaseGate()
            gate.policy = object()  # type: ignore[assignment]
            with self.subTest(status=status):
                self.assertFalse(gate.check(dossier).valid)

        gate = ReleaseGate()
        gate.policy = object()  # type: ignore[assignment]
        report = gate.check(self.draft)
        self.assertEqual(
            {item.code for item in report.issues},
            {"invalid_release_policy", "release_status_required"},
        )

    def test_edge_aggregate_and_context_are_recomputed(self) -> None:
        hypothesis = self.draft.hypotheses[0]
        edge_index = next(
            index
            for index, edge in enumerate(hypothesis.edges)
            if edge.edge_type.value != "causal_path"
        )
        original_edge = hypothesis.edges[edge_index]
        changed_support = 0.0 if original_edge.support != 0.0 else 1.0
        changed_edge = replace(original_edge, support=changed_support)
        edges = list(hypothesis.edges)
        edges[edge_index] = changed_edge
        forged = _readdress(
            replace(
                self.draft,
                hypotheses=(replace(hypothesis, edges=tuple(edges)),),
            )
        )

        report = ContractValidator().validate_dossier(forged)
        self.assertFalse(report.valid)
        self.assertIn("edge_aggregate_mismatch", {item.code for item in report.issues})

        changed_context = replace(self.draft.evidence[0].context, cell_state="other-state")
        changed_claim = replace(self.draft.evidence[0], context=changed_context)
        forged = _readdress(
            replace(self.draft, evidence=(changed_claim,) + self.draft.evidence[1:])
        )
        report = ContractValidator().validate_dossier(forged)
        self.assertIn("mixed_dossier_context", {item.code for item in report.issues})
        self.assertIn("invalid_evidence_graph", {item.code for item in report.issues})

    def test_issue_output_is_bounded_and_deterministic(self) -> None:
        forged = _readdress(
            replace(
                self.draft,
                research_use_only=False,
                source_bundle_addresses=("sha256:not-a-digest",),
            )
        )
        validator = ContractValidator(limits=ValidationLimits(max_issues=2))

        first = validator.validate_dossier(forged)
        second = validator.validate_dossier(forged)

        self.assertFalse(first.valid)
        self.assertLessEqual(len(first.issues), 2)
        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual(
            first.issues,
            tuple(
                sorted(
                    first.issues,
                    key=lambda issue: (
                        issue.path,
                        issue.code,
                        issue.severity.value,
                        issue.message,
                        issue.remediation,
                    ),
                )
            ),
        )


if __name__ == "__main__":
    unittest.main()
