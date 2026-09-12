"""Adversarial tests for the bounded dossier validation and release boundary."""

from __future__ import annotations

import copy
import tempfile
import unittest
from collections.abc import Mapping, Sequence
from dataclasses import replace
from typing import Any
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
from glio_noncode.serialization import canonical_bytes, content_hash
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


def _minimal_receipt(*, url: str = "http://a") -> dict[str, Any]:
    return FetchReceipt(
        source_id="A",
        source_version="1",
        url=url,
        request_hash="sha256:" + "0" * 64,
        response_hash="sha256:" + "0" * 64,
        status=FetchStatus.FETCHED,
        http_status=200,
        attempts=1,
        retrieved_at="0001-01-01T00:00:00+00:00",
        elapsed_seconds=None,
        cache_expires_at=None,
    ).to_dict()


def _json_string_characters(value: object) -> int:
    if type(value) is str:
        return len(value)
    if isinstance(value, Mapping):
        return sum(
            _json_string_characters(key) + _json_string_characters(item)
            for key, item in value.items()
        )
    if isinstance(value, Sequence):
        return sum(_json_string_characters(item) for item in value)
    return 0


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

    def test_source_bundle_limit_covers_every_maximal_live_stage(self) -> None:
        expected = 3 * validation_module.MAX_VALIDATION_VARIANTS + 6
        self.assertEqual(validation_module.MAX_VALIDATION_SOURCE_BUNDLES, expected)
        self.assertEqual(ValidationLimits().max_source_bundles, expected)

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
        with patch.object(validation_module, "MAX_VALIDATION_SOURCE_BUNDLES", 1_000_000):
            with self.assertRaisesRegex(ValidationError, "safety ceiling"):
                ValidationLimits(max_source_bundles=3_007)

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

    def test_more_than_legacy_node_boundary_receipts_validate_by_default(self) -> None:
        receipt_count = 34_443
        one_receipt = replace(self.draft, source_receipts=(_minimal_receipt(),))
        expanded = copy.copy(self.draft)
        object.__setattr__(
            expanded,
            "source_receipts",
            (one_receipt.source_receipts[0],) * receipt_count,
        )
        object.__setattr__(
            expanded,
            "source_bundle_addresses",
            ("sha256:" + "1" * 64,),
        )
        body = expanded.to_dict()
        body.pop("content_address")
        object.__setattr__(expanded, "content_address", content_hash(body))

        report = ContractValidator().validate_dossier(expanded)

        self.assertGreater(receipt_count, 34_442)
        self.assertTrue(report.valid, report.to_dict())

    def test_aggregate_budget_admission_precedes_receipt_parsing(self) -> None:
        one_receipt = replace(self.draft, source_receipts=(_minimal_receipt(),))
        expanded = copy.copy(self.draft)
        object.__setattr__(
            expanded,
            "source_receipts",
            (one_receipt.source_receipts[0],) * 100,
        )

        with patch.object(
            validation_module,
            "_parse_receipt",
            wraps=validation_module._parse_receipt,
        ) as parse_receipt:
            report = ContractValidator(
                limits=ValidationLimits(max_total_characters=1)
            ).validate_dossier(expanded)

        self.assertEqual({issue.code for issue in report.issues}, {"validation_limit_exceeded"})
        parse_receipt.assert_not_called()

    def test_oversized_receipt_collections_reject_before_iteration(self) -> None:
        oversized_mapping = validation_module._FrozenJsonObject(
            {f"field-{index}": None for index in range(15)}
        )
        with patch.object(
            validation_module,
            "set",
            side_effect=AssertionError("iterated oversized mapping"),
            create=True,
        ) as set_:
            with self.assertRaisesRegex(ValidationError, "exactly 14 fields"):
                validation_module._parse_receipt(oversized_mapping)
        set_.assert_not_called()

        raw = _minimal_receipt()
        raw["warnings"] = validation_module._FrozenJsonArray(["warning"] * 257)
        oversized_warnings = validation_module._FrozenJsonObject(raw)
        with patch.object(
            validation_module._FrozenJsonArray,
            "__iter__",
            side_effect=AssertionError("iterated oversized warnings"),
        ) as iterate:
            with self.assertRaisesRegex(ValidationError, "safety ceiling of 256 items"):
                validation_module._parse_receipt(oversized_warnings)
        iterate.assert_not_called()

    def test_full_receipt_boundary_fits_joint_default_budgets(self) -> None:
        receipt = _minimal_receipt()
        receipt_count = validation_module.MAX_VALIDATION_SOURCE_RECEIPTS
        base = _readdress(
            replace(
                self.draft,
                source_bundle_addresses=("sha256:" + "1" * 64,),
            )
        )
        raw = base.to_dict()
        self.assertEqual(raw["source_receipts"], [])

        receipt_bytes = len(canonical_bytes(receipt))
        receipt_array_bytes = 2 + receipt_count * receipt_bytes + receipt_count - 1
        full_payload_bytes = len(canonical_bytes(raw)) - len(b"[]") + receipt_array_bytes
        # This is conservative: canonical JSON also spells typed-model field names,
        # while structured validation charges mapping keys but not dataclass field names.
        full_string_characters = (
            _json_string_characters(raw)
            + receipt_count * _json_string_characters(receipt)
        )
        limits = ValidationLimits()
        self.assertLessEqual(full_payload_bytes, limits.max_canonical_bytes)
        self.assertLessEqual(full_string_characters, limits.max_total_characters)

        one_receipt = replace(base, source_receipts=(receipt,))
        boundary = copy.copy(base)
        object.__setattr__(
            boundary,
            "source_receipts",
            (one_receipt.source_receipts[0],) * receipt_count,
        )
        validation_module._dossier_preflight(boundary, limits)
        validation_module._measure_model(
            boundary,
            limits,
            compact_source_receipts=b"\x01" * receipt_count,
        )

    def test_receipt_compaction_preserves_malformed_node_character_and_depth_limits(
        self,
    ) -> None:
        malformed = _minimal_receipt()
        malformed["unexpected"] = [None] * 64
        stripped = replace(
            self.draft,
            hypotheses=(),
            evidence=(),
            experiments=(),
            review=None,
            warnings=(),
            source_receipts=(malformed,),
            source_bundle_addresses=(),
        )
        report = ContractValidator(
            limits=ValidationLimits(max_structured_nodes=64)
        ).validate_dossier(stripped)
        self.assertEqual({issue.code for issue in report.issues}, {"validation_limit_exceeded"})
        self.assertIn(".unexpected[", report.issues[0].path)

        long_receipt = _minimal_receipt(url="http://a/" + "x" * 2_048)
        compact = replace(stripped, source_receipts=(long_receipt,))
        character_report = ContractValidator(
            limits=ValidationLimits(max_total_characters=2_000)
        ).validate_dossier(compact)
        self.assertEqual(
            {issue.code for issue in character_report.issues},
            {"validation_limit_exceeded"},
        )
        self.assertEqual(character_report.issues[0].path, "Dossier.source_receipts[0].url")

        string_report = ContractValidator(
            limits=ValidationLimits(max_string_characters=2_000)
        ).validate_dossier(compact)
        self.assertEqual(
            {issue.code for issue in string_report.issues},
            {"validation_limit_exceeded"},
        )
        self.assertEqual(string_report.issues[0].path, "Dossier.source_receipts[0].url")

        depth_report = ContractValidator(
            limits=ValidationLimits(max_structured_depth=2)
        ).validate_dossier(replace(stripped, source_receipts=(_minimal_receipt(),)))
        self.assertEqual(
            {issue.code for issue in depth_report.issues},
            {"validation_limit_exceeded"},
        )
        self.assertEqual(
            depth_report.issues[0].path,
            "Dossier.source_receipts[0].<key>",
        )

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
