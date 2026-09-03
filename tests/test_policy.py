"""Adversarial checks for the bounded research-use policy boundary."""

from __future__ import annotations

import copy
import tempfile
import unittest
from dataclasses import replace

import glio_noncode.policy as policy_module
from glio_noncode.errors import PolicyViolation, ValidationError
from glio_noncode.models import Dossier, ResearchStatus, ReviewDecision, ReviewState
from glio_noncode.policy import (
    MAX_POLICY_PATTERN_MATCHES,
    MAX_POLICY_TEXT_ITEMS,
    PolicyDecision,
    PolicyLimits,
    ResearchPolicy,
)
from glio_noncode.runtime import CaseRuntime
from glio_noncode.validation import ReleaseGate

from .helpers import fixture_manifest


class ResearchPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._directory = tempfile.TemporaryDirectory()
        cls.runtime = CaseRuntime(cls._directory.name)
        cls.dossier = cls.runtime.evaluate(fixture_manifest())

    @classmethod
    def tearDownClass(cls) -> None:
        cls._directory.cleanup()

    def _review(
        self,
        state: ReviewState,
        rationale: str = "Research review completed.",
    ) -> ReviewDecision:
        return ReviewDecision(
            review_id=f"review-{state.value}",
            case_id=self.dossier.case_id,
            reviewer="scientific-reviewer",
            state=state,
            reviewed_hypothesis_ids=(self.dossier.hypotheses[0].hypothesis_id,),
            rationale=rationale,
            checked_claim_ids=tuple(claim.evidence_id for claim in self.dossier.evidence),
        )

    def test_asserted_boundary_claims_are_detected_once_across_spelling_variants(self) -> None:
        decision = ResearchPolicy().inspect_texts(
            (
                "Diagnosis: glioblastoma; diagnosis confirmed.",
                "We recommend treatment and list a therapy-recommendation.",
                "This variant is pathogenic.",
                "Trial_eligibility is confirmed.",
                "The result is clinically-actionable.",
                "This is a patient specific conclusion.",
            )
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(
            decision.violations,
            (
                "diagnostic claim",
                "treatment recommendation",
                "pathogenicity claim",
                "trial eligibility claim",
                "clinical actionability claim",
                "patient-specific claim",
            ),
        )

    def test_unicode_compatibility_and_separator_variants_cannot_bypass_checks(self) -> None:
        policy = ResearchPolicy()

        decision = policy.inspect_texts(
            (
                "Ｄｉａｇｎｏｓｉｓ: glioblastoma.",
                "This is patient‑specific.",
                "This is patient֊specific.",
            )
        )
        hidden = policy.inspect_texts(("diag\u200bnosis: glioblastoma.",))
        variation_selector = policy.inspect_texts(("diag\ufe0fnosis: glioblastoma.",))

        self.assertEqual(
            decision.violations,
            ("diagnostic claim", "patient-specific claim"),
        )
        self.assertEqual(
            hidden.violations,
            ("policy text contains unsupported control characters",),
        )
        self.assertEqual(variation_selector.violations, hidden.violations)

        split_tokens = (
            "This is patient\u2043specific.",
            "diag\u200anosis: glioblastoma.",
            "diag\u2800nosis: glioblastoma.",
            "diag\u0338nosis: glioblastoma.",
            "diag\u2043nosis: glioblastoma.",
            "diag/nosis: glioblastoma.",
            "patient\u2800specific result.",
            "p\u0430thogenic variant.",
            "d\u00edagnosis: glioblastoma.",
            "pathog\u00e9nic variant.",
            "diag\u2044nosis: glioblastoma.",
            "diag\u2215nosis: glioblastoma.",
            "diag\u00d7nosis: glioblastoma.",
            "diag\U0001f525nosis: glioblastoma.",
            "diag nosis: glioblastoma.",
            "\u0440athogenic variant.",
        )
        for text in split_tokens:
            with self.subTest(text=text):
                self.assertFalse(policy.inspect_texts((text,)).allowed)

    def test_unordered_iterables_still_produce_canonical_violation_order(self) -> None:
        decision = ResearchPolicy().inspect_texts(
            {"This is pathogenic.", "Diagnosis: glioblastoma."}
        )

        self.assertEqual(
            decision.violations,
            ("diagnostic claim", "pathogenicity claim"),
        )

    def test_explicit_research_limitations_and_uncertainty_remain_allowed(self) -> None:
        decision = ResearchPolicy().inspect_texts(
            (
                "The analysis does not provide a diagnosis or treatment recommendation.",
                "Pathogenicity remains uncertain.",
                "Trial eligibility is outside scope.",
                "Eligibility for a clinical trial has not been determined.",
                "No clinically actionable conclusion is made.",
                "No patient-specific inference is provided.",
                "No diagnosis is made and treatment is not recommended.",
                "Regulatory mechanism is a research hypothesis requiring validation.",
                "We cannot diagnose from these data.",
                "The assay is non-diagnostic.",
                "Diagnostic performance was not evaluated.",
                "We cannot conclude a diagnosis from these data.",
                "The model diagnostic performance was measured.",
                "No \u201cdiagnosis\u201d is made.",
                "The treatment recommendation should not be followed.",
                "The analysis doesn\u2019t provide a diagnosis.",
                "Trial eligibility is currently unknown.",
                "Diagnosis has not yet been determined.",
                "Pathogenicity testing was inconclusive.",
                "No definitive diagnosis can be made from these data.",
                "We are unable to diagnose from these data.",
                "No treatment recommendation can be made from these data.",
                "Diagnosis cannot currently be determined.",
            )
        )

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.violations, ())

    def test_negation_cannot_mask_a_later_assertion_in_another_clause(self) -> None:
        policy = ResearchPolicy()

        for text in (
            "This is not a diagnosis; diagnosis: glioblastoma.",
            "We do not diagnose, but the diagnosis is glioblastoma.",
            "Pathogenicity is uncertain; however, the variant is pathogenic.",
            "No ambiguity exists and diagnosis: glioblastoma.",
            "The result is not weak and is clinically actionable.",
            "There is no uncertainty: this variant is pathogenic.",
            "No unrelated warning, patient-specific result follows.",
            "Treatment is recommended.",
            "Eligible for a clinical trial.",
            "We do not provide evidence and diagnosis: glioblastoma.",
            "Pathogenicity is not uncertain.",
            "Pathogenicity is uncertain and ultimately confirmed.",
            "We do not provide caveats and conclude a diagnosis of glioblastoma.",
            "We do not provide advice\u2028Diagnosis favors glioblastoma.",
            "We do not provide advice\u3002Diagnosis favors glioblastoma.",
            "We cannot provide generic guidance, although diagnosis favors glioblastoma.",
            "The variant is not pathogenic.",
            "Patient is not eligible for a clinical trial.",
            "The result is not clinically actionable.",
            "No diagnosis except glioblastoma.",
            "Diagnosis is unknown, but glioblastoma.",
            "We cannot diagnose; however glioblastoma.",
            "We cannot diagnose, but conclude glioblastoma.",
            "We do not recommend treatment, but advise temozolomide.",
            "Diagnosis is not established; it is glioblastoma.",
            "Diagnosis is unknown, likely glioblastoma.",
            "Trial eligibility is unknown, likely eligible.",
        ):
            with self.subTest(text=text):
                self.assertFalse(policy.inspect_texts((text,)).allowed)

    def test_identifier_and_obvious_morphology_variants_cannot_bypass_checks(self) -> None:
        policy = ResearchPolicy()

        cases = {
            "diagnosis_confirmed: glioblastoma": "diagnostic claim",
            "pathogenicity_score=.99": "pathogenicity claim",
            "trial_eligibility_confirmed=true": "trial eligibility claim",
            "Chemotherapy is recommended.": "treatment recommendation",
            "We recommend temozolomide.": "treatment recommendation",
            "We recommend no treatment.": "treatment recommendation",
            "The patient was rediagnosed yesterday.": "diagnostic claim",
            "This variant is nonpathogenic.": "pathogenicity claim",
            "The patient is ineligible for a clinical trial.": "trial eligibility claim",
            "Clinical actionability is established.": "clinical actionability claim",
        }
        for text, violation in cases.items():
            with self.subTest(text=text):
                self.assertIn(violation, policy.inspect_texts((text,)).violations)

    def test_text_input_is_strict_and_enforcement_raises_policy_violation(self) -> None:
        policy = ResearchPolicy()

        for value in (
            "diagnosis",
            b"diagnosis",
            {"text": "diagnosis"},
            (123,),
        ):
            with self.subTest(value=value):
                decision = policy.inspect_texts(value)  # type: ignore[arg-type]
                self.assertFalse(decision.allowed)
                self.assertIn("iterable of strings", decision.violations[0])

        with self.assertRaisesRegex(PolicyViolation, "iterable of strings"):
            policy.enforce_texts("safe research text")

    def test_iterator_failure_is_converted_to_a_fail_closed_decision(self) -> None:
        def failing_values():
            yield "bounded research hypothesis"
            raise RuntimeError("caller iterator failed")

        class FailingIterable:
            def __iter__(self):
                raise RuntimeError("caller iteration setup failed")

        policy = ResearchPolicy()
        decision = policy.inspect_texts(failing_values())
        setup_decision = policy.inspect_texts(FailingIterable())

        self.assertFalse(decision.allowed)
        self.assertEqual(
            decision.violations,
            ("policy text input could not be inspected safely",),
        )
        self.assertEqual(setup_decision.violations, decision.violations)

    def test_infinite_iterable_consumes_only_one_count_sentinel(self) -> None:
        yielded = 0

        def infinite_values():
            nonlocal yielded
            while True:
                yielded += 1
                yield "bounded research hypothesis"

        policy = ResearchPolicy(limits=PolicyLimits(max_text_items=3))
        decision = policy.inspect_texts(infinite_values())

        self.assertFalse(decision.allowed)
        self.assertEqual(yielded, 4)
        self.assertTrue(
            any("configured maximum of 3 items" in item for item in decision.violations)
        )

    def test_per_text_and_total_character_work_is_bounded_before_regex_scans(self) -> None:
        long_text = ResearchPolicy(limits=PolicyLimits(max_text_characters=5)).inspect_texts(
            ("123456",)
        )
        total_text = ResearchPolicy(
            limits=PolicyLimits(max_text_characters=10, max_total_characters=5)
        ).inspect_texts(("123", "456"))

        self.assertEqual(
            long_text.violations,
            ("policy text exceeds the configured maximum of 5 characters",),
        )
        self.assertEqual(
            total_text.violations,
            ("policy text input exceeds the configured maximum of 5 total characters",),
        )

        dossier_decision = ResearchPolicy(limits=PolicyLimits(max_text_items=2)).validate_dossier(
            self.dossier
        )
        self.assertFalse(dossier_decision.allowed)
        self.assertTrue(
            any("configured maximum of 2 items" in item for item in dossier_decision.violations)
        )

    def test_safe_pattern_matches_have_a_separate_work_ceiling(self) -> None:
        policy = ResearchPolicy(limits=PolicyLimits(max_pattern_matches=3))

        decision = policy.inspect_texts(("Pathogenicity remains uncertain. " * 4,))

        self.assertFalse(decision.allowed)
        self.assertEqual(
            decision.violations,
            ("policy pattern matching exceeds the configured maximum of 3 candidates",),
        )

    def test_policy_limits_are_exact_integers_and_can_only_be_lowered(self) -> None:
        for value in (True, 1.5, "3"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValidationError, "must be an integer"):
                    PolicyLimits(max_text_items=value)  # type: ignore[arg-type]
        with self.assertRaisesRegex(ValidationError, "must be positive"):
            PolicyLimits(max_text_items=0)
        with self.assertRaisesRegex(ValidationError, "safety ceiling"):
            PolicyLimits(max_text_items=MAX_POLICY_TEXT_ITEMS + 1)
        with self.assertRaisesRegex(ValidationError, "safety ceiling"):
            PolicyLimits(max_pattern_matches=MAX_POLICY_PATTERN_MATCHES + 1)
        with self.assertRaisesRegex(ValidationError, "limits must be PolicyLimits"):
            ResearchPolicy(limits={})  # type: ignore[arg-type]
        with self.assertRaisesRegex(ValidationError, "valid PolicyLimits"):
            ResearchPolicy(limits=object.__new__(PolicyLimits))

        mutated = PolicyLimits()
        object.__setattr__(mutated, "max_text_items", MAX_POLICY_TEXT_ITEMS + 1)
        with self.assertRaisesRegex(ValidationError, "safety ceiling"):
            ResearchPolicy(limits=mutated)

        original_ceiling = policy_module.MAX_POLICY_TEXT_ITEMS
        try:
            policy_module.MAX_POLICY_TEXT_ITEMS = 10**12
            with self.assertRaisesRegex(ValidationError, "safety ceiling"):
                PolicyLimits(max_text_items=10**12)
        finally:
            policy_module.MAX_POLICY_TEXT_ITEMS = original_ceiling

        pattern_mutated = ResearchPolicy()
        pattern_mutated._blocked_patterns = ()
        self.assertFalse(pattern_mutated.inspect_texts(("Diagnosis: glioblastoma.",)).allowed)

        policy = ResearchPolicy()
        policy.limits = object()  # type: ignore[assignment]
        self.assertEqual(policy.inspect_texts(("safe",)).violations, ("policy limits are invalid",))

        policy = ResearchPolicy()
        object.__setattr__(policy.limits, "max_text_items", -1)
        self.assertEqual(policy.inspect_texts(("safe",)).violations, ("policy limits are invalid",))

    def test_generated_dossiers_and_accepted_releases_remain_allowed(self) -> None:
        policy = ResearchPolicy()
        accepted = self.runtime.review(
            self.dossier,
            self._review(ReviewState.ACCEPTED),
        )

        self.assertTrue(policy.validate_dossier(self.dossier).allowed)
        self.assertTrue(policy.validate_dossier(accepted).allowed)
        self.assertTrue(ReleaseGate(policy).check(accepted).valid)
        self.assertTrue(accepted.is_releasable)

        legacy = replace(self.dossier, policy_version="research-boundary-2026.08")
        self.assertTrue(policy.validate_dossier(legacy).allowed)
        unsupported = replace(self.dossier, policy_version="clinical-boundary-custom")
        self.assertIn(
            "dossier policy version is unsupported",
            policy.validate_dossier(unsupported).violations,
        )

        oversized = copy.copy(self.dossier)
        object.__setattr__(oversized, "policy_version", "x" * 70_000)
        oversized_decision = policy.validate_dossier(oversized)
        self.assertFalse(oversized_decision.allowed)
        self.assertIn("dossier policy version is invalid", oversized_decision.violations)

    def test_released_dossier_requires_an_accepted_review_state(self) -> None:
        policy = ResearchPolicy()

        for state in (ReviewState.PENDING, ReviewState.REJECTED, ReviewState.RETURNED):
            forged = replace(
                self.dossier,
                status=ResearchStatus.RELEASED_RESEARCH,
                review=self._review(state),
            )
            with self.subTest(state=state):
                decision = policy.validate_dossier(forged)
                self.assertFalse(decision.allowed)
                self.assertIn(
                    "released dossier review decision is not accepted",
                    decision.violations,
                )
                self.assertFalse(ReleaseGate(policy).check(forged).valid)
                self.assertFalse(forged.is_releasable)

        missing = replace(
            self.dossier,
            status=ResearchStatus.RELEASED_RESEARCH,
            review=None,
        )
        self.assertIn(
            "released dossier has no review decision",
            policy.validate_dossier(missing).violations,
        )
        self.assertFalse(missing.is_releasable)

    def test_policy_decisions_are_exact_and_retain_the_canonical_warning(self) -> None:
        warning = "All outputs are research-use only and require expert review."
        valid = PolicyDecision(
            allowed=True,
            policy_version=ResearchPolicy.version,
            violations=(),
            warnings=(warning,),
        )
        self.assertTrue(valid.allowed)

        invalid_values = (
            {"allowed": 1, "violations": (), "warnings": (warning,)},
            {"allowed": True, "violations": ("blocked",), "warnings": (warning,)},
            {"allowed": False, "violations": (), "warnings": (warning,)},
            {"allowed": True, "violations": (), "warnings": ("replacement",)},
            {"allowed": True, "violations": [], "warnings": (warning,)},
            {"allowed": False, "violations": (" padded ",), "warnings": (warning,)},
            {
                "allowed": True,
                "policy_version": "clinical-release",
                "violations": (),
                "warnings": (warning,),
            },
        )
        for overrides in invalid_values:
            values = {
                "allowed": True,
                "policy_version": ResearchPolicy.version,
                "violations": (),
                "warnings": (warning,),
                **overrides,
            }
            with self.subTest(overrides=overrides), self.assertRaises(ValidationError):
                PolicyDecision(**values)  # type: ignore[arg-type]

        denied = ResearchPolicy().inspect_texts(("Diagnosis: glioblastoma.",))
        object.__setattr__(denied, "allowed", True)
        object.__setattr__(denied, "violations", ())
        with self.assertRaisesRegex(ValidationError, "mutated"):
            denied.to_dict()

        policy = ResearchPolicy()
        policy.version = "forged-version"
        policy.supported_versions = frozenset({"forged-version"})
        decision = policy.inspect_texts(("bounded research result",))
        self.assertEqual(decision.policy_version, ResearchPolicy.version)
        forged = replace(self.dossier, policy_version="forged-version")
        self.assertIn(
            "dossier policy version is unsupported",
            policy.validate_dossier(forged).violations,
        )

        mismatched_review = replace(
            self._review(ReviewState.ACCEPTED),
            case_id="different-case",
        )
        mismatched = replace(
            self.dossier,
            status=ResearchStatus.RELEASED_RESEARCH,
            review=mismatched_review,
        )
        self.assertFalse(mismatched.is_releasable)
        self.assertIn(
            "dossier structure is invalid",
            policy.validate_dossier(mismatched).violations,
        )

    def test_accepted_review_requires_released_research_status(self) -> None:
        policy = ResearchPolicy()

        for status in (
            ResearchStatus.DRAFT,
            ResearchStatus.REVIEW_REQUIRED,
            ResearchStatus.REVIEWED,
            ResearchStatus.SUPERSEDED,
        ):
            forged = replace(
                self.dossier,
                status=status,
                review=self._review(ReviewState.ACCEPTED),
            )
            with self.subTest(status=status):
                decision = policy.validate_dossier(forged)
                self.assertFalse(decision.allowed)
                self.assertIn(
                    "accepted review is attached to a non-released dossier status",
                    decision.violations,
                )
                self.assertFalse(ReleaseGate(policy).check(forged).valid)
                self.assertFalse(forged.is_releasable)

    def test_reviewed_status_requires_a_review_record(self) -> None:
        forged = replace(self.dossier, status=ResearchStatus.REVIEWED, review=None)

        decision = ResearchPolicy().validate_dossier(forged)

        self.assertFalse(decision.allowed)
        self.assertIn("reviewed dossier has no review decision", decision.violations)

    def test_all_human_facing_dossier_text_surfaces_are_inspected(self) -> None:
        policy = ResearchPolicy()
        option = self.dossier.experiments[0]
        unsafe_option = replace(
            option,
            limitations=option.limitations + ("Treatment recommendation: drug X.",),
        )
        unsafe_hypothesis = replace(
            self.dossier.hypotheses[0],
            alternatives=("Diagnosis: glioblastoma.",),
        )
        forged = replace(
            self.dossier,
            hypotheses=(unsafe_hypothesis,) + self.dossier.hypotheses[1:],
            experiments=(unsafe_option,) + self.dossier.experiments[1:],
            review=self._review(
                ReviewState.ACCEPTED,
                "The result is clinically actionable.",
            ),
            warnings=("A treatment recommendation was added.",),
        )

        decision = policy.validate_dossier(forged)

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.violations.count("treatment recommendation"), 1)
        self.assertIn("diagnostic claim", decision.violations)
        self.assertIn("clinical actionability claim", decision.violations)

    def test_structured_payloads_receipts_and_mapping_keys_are_inspected(self) -> None:
        policy = ResearchPolicy()
        unsafe_claim = replace(
            self.dossier.evidence[0],
            payload={
                "provider_finding": {"text": "Diagnosis: glioblastoma."},
                "Treatment recommendation: drug X.": True,
            },
        )
        forged = replace(
            self.dossier,
            evidence=(unsafe_claim,) + self.dossier.evidence[1:],
            source_receipts=({"warning": "This finding is clinically actionable."},),
        )

        decision = policy.validate_dossier(forged)

        self.assertFalse(decision.allowed)
        self.assertIn("diagnostic claim", decision.violations)
        self.assertIn("treatment recommendation", decision.violations)
        self.assertIn("clinical actionability claim", decision.violations)
        self.assertEqual(decision.violations.count("diagnostic claim"), 1)

    def test_nested_structure_traversal_is_charged_even_when_text_tuples_are_empty(
        self,
    ) -> None:
        option = self.dossier.experiments[0]
        empty_options = tuple(
            replace(
                option,
                option_id=f"option-{index}",
                required_context=(),
                controls=(),
                readouts=(),
                limitations=(),
            )
            for index in range(20)
        )
        sparse = replace(
            self.dossier,
            hypotheses=(),
            evidence=(),
            experiments=empty_options,
        )

        decision = ResearchPolicy(limits=PolicyLimits(max_text_items=20)).validate_dossier(sparse)

        self.assertFalse(decision.allowed)
        self.assertIn(
            "policy text input exceeds the configured maximum of 20 items",
            decision.violations,
        )

    def test_direct_object_and_nested_type_misuse_fail_closed_without_exceptions(self) -> None:
        policy = ResearchPolicy()
        self.assertEqual(
            policy.validate_dossier(object()).violations,  # type: ignore[arg-type]
            ("dossier must be a Dossier",),
        )
        self.assertEqual(
            policy.validate_dossier(object.__new__(Dossier)).violations,
            ("dossier policy text fields are malformed",),
        )

        partial_review = object.__new__(ReviewDecision)
        object.__setattr__(partial_review, "state", ReviewState.ACCEPTED)
        partial = object.__new__(Dossier)
        object.__setattr__(partial, "status", ResearchStatus.RELEASED_RESEARCH)
        object.__setattr__(partial, "research_use_only", True)
        object.__setattr__(partial, "review", partial_review)
        self.assertFalse(partial.is_releasable)

        malformed_nested = replace(self.dossier, experiments=(object(),))
        nested_decision = policy.validate_dossier(malformed_nested)
        self.assertFalse(nested_decision.allowed)
        self.assertIn("dossier policy text fields are malformed", nested_decision.violations)

        coercive_flag = copy.copy(self.dossier)
        object.__setattr__(coercive_flag, "research_use_only", "true")
        flag_decision = policy.validate_dossier(coercive_flag)
        self.assertFalse(flag_decision.allowed)
        self.assertIn("research-use flag missing", flag_decision.violations)

        coercive_status = replace(self.dossier, status="released_research")
        status_decision = policy.validate_dossier(coercive_status)
        self.assertFalse(status_decision.allowed)
        self.assertIn("dossier research status is invalid", status_decision.violations)

        malformed_review = replace(
            self.dossier,
            status=ResearchStatus.RELEASED_RESEARCH,
            review=object(),
        )
        review_decision = policy.validate_dossier(malformed_review)
        self.assertFalse(review_decision.allowed)
        self.assertIn("dossier review decision is invalid", review_decision.violations)
        self.assertIn(
            "released dossier review decision is not accepted",
            review_decision.violations,
        )

        uninitialized_review = replace(
            self.dossier,
            status=ResearchStatus.RELEASED_RESEARCH,
            review=object.__new__(ReviewDecision),
        )
        uninitialized_decision = policy.validate_dossier(uninitialized_review)
        self.assertFalse(uninitialized_decision.allowed)
        self.assertIn(
            "dossier policy text fields are malformed",
            uninitialized_decision.violations,
        )
        self.assertIn(
            "released dossier review decision is not accepted",
            uninitialized_decision.violations,
        )

        coercive_review = copy.copy(self._review(ReviewState.ACCEPTED))
        object.__setattr__(coercive_review, "state", "accepted")
        coercive_review_dossier = replace(
            self.dossier,
            status=ResearchStatus.RELEASED_RESEARCH,
            review=coercive_review,
        )
        coercive_review_decision = policy.validate_dossier(coercive_review_dossier)
        self.assertFalse(coercive_review_decision.allowed)
        self.assertIn(
            "dossier review state is invalid",
            coercive_review_decision.violations,
        )
        self.assertIn(
            "released dossier review decision is not accepted",
            coercive_review_decision.violations,
        )


if __name__ == "__main__":
    unittest.main()
