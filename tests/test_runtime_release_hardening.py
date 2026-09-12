"""Adversarial coverage for transactional runtime review and release."""

from __future__ import annotations

import json
import math
import tempfile
import threading
import unittest
from dataclasses import replace
from pathlib import Path
from queue import Queue
from typing import Any, cast
from unittest.mock import patch

import glio_noncode._callback_isolation as callback_isolation_module
import glio_noncode.context as context_module
import glio_noncode.data_sources as data_sources_module
import glio_noncode.expression_claims as expression_claims_module
import glio_noncode.hypotheses as hypotheses_module
import glio_noncode.policy as policy_module
import glio_noncode.runtime as runtime_module
import glio_noncode.sequence_inference as sequence_inference_module
import glio_noncode.storage as storage_module
from glio_noncode.atlas import PublicAtlasRetriever
from glio_noncode.data_sources import (
    EnrichmentResult,
    PublicReferenceRetriever,
    ReferenceBundle,
    ReferenceRetrievalLimits,
    RetryPolicy,
    SourceClient,
    TransportResponse,
    UrllibTransport,
)
from glio_noncode.errors import StoreError, ValidationError
from glio_noncode.experiments import ExperimentPlanner, ExperimentPlanningLimits
from glio_noncode.expression_evidence import (
    AllelicDirection,
    ExpressionDirection,
    RegulatoryDirection,
    RNAConsequenceEvidence,
    RNAEvidenceState,
)
from glio_noncode.hypotheses import HypothesisBuilder
from glio_noncode.models import (
    CaseManifest,
    Dossier,
    EvidenceState,
    ResearchStatus,
    ReviewDecision,
    ReviewState,
)
from glio_noncode.policy import ResearchPolicy
from glio_noncode.reference_manifest import ReferenceAccessMode
from glio_noncode.reference_registry import CoordinateSystem
from glio_noncode.reference_track_adapters import (
    DeclaredReferenceTrackAdapter,
    ReferenceTrackAdapterRegistry,
    ReferenceTrackMetadata,
)
from glio_noncode.runtime import CaseRuntime
from glio_noncode.sequence_inference import SequenceInference
from glio_noncode.serialization import content_hash
from glio_noncode.storage import ObjectStore, RunStore
from glio_noncode.validation import (
    ContractValidator,
    IssueSeverity,
    ReleaseGate,
    ValidationIssue,
    ValidationReport,
)

from .helpers import fixture_manifest


def _review(
    dossier: Dossier,
    *,
    state: ReviewState = ReviewState.ACCEPTED,
    review_id: str = "review-runtime-hardening",
    hypothesis_ids: tuple[str, ...] | None = None,
    claim_ids: tuple[str, ...] | None = None,
) -> ReviewDecision:
    return ReviewDecision(
        review_id=review_id,
        case_id=dossier.case_id,
        reviewer="scientific-reviewer",
        state=state,
        reviewed_hypothesis_ids=(
            tuple(item.hypothesis_id for item in dossier.hypotheses)
            if hypothesis_ids is None
            else hypothesis_ids
        ),
        rationale="Reviewed the snapshot while retaining uncertainty and research-only use.",
        checked_claim_ids=(
            tuple(item.evidence_id for item in dossier.evidence) if claim_ids is None else claim_ids
        ),
    )


def _runtime_state(runtime: CaseRuntime, dossier: Dossier) -> tuple[object, object, frozenset[str]]:
    run_record = runtime.get_run(dossier.run_id)
    cached_log = runtime._logs[dossier.run_id].to_record()
    object_names = frozenset(path.name for path in runtime.store.store.objects.glob("*.json"))
    return run_record, cached_log, object_names


def _rna_consequence() -> RNAConsequenceEvidence:
    manifest = fixture_manifest()
    prediction_id = "prediction:runtime:hardening"
    return RNAConsequenceEvidence(
        prediction_id=prediction_id,
        prediction_address=content_hash(
            {"prediction_id": prediction_id},
            prefix="regulatory-effect-prediction",
        ),
        variant_id=manifest.variants[0].variant_id,
        feature_id=manifest.candidate_elements[0].target_genes[0],
        context_key=manifest.context.key,
        predicted_direction=RegulatoryDirection.GAIN,
        state=RNAEvidenceState.SUPPORTED,
        expression_state=RNAEvidenceState.SUPPORTED,
        expression_direction=ExpressionDirection.UP,
        expression_robust_z=7.0,
        expression_result_address=content_hash(
            {"prediction_id": prediction_id, "component": "expression"},
            prefix="expression-outlier",
        ),
        allelic_state=RNAEvidenceState.SUPPORTED,
        allelic_direction=AllelicDirection.ALT_ENRICHED,
        allelic_log2_ratio=2.0,
        allelic_q_value=0.001,
        allelic_result_address=content_hash(
            {"prediction_id": prediction_id, "component": "allelic"},
            prefix="allelic-imbalance",
        ),
        reason_codes=("runtime_hardening_supported",),
    )


class RuntimeReleaseHardeningTests(unittest.TestCase):
    def test_partial_hypothesis_acceptance_cannot_release_current_snapshot(self) -> None:
        manifest = fixture_manifest()
        first_variant = manifest.variants[0]
        second_variant = replace(
            first_variant,
            variant_id="var-demo-002",
            start=first_variant.start + 10,
            end=first_variant.end + 10,
            reference="C",
            alternate="T",
        )
        manifest = replace(manifest, variants=(first_variant, second_variant))
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            dossier = runtime.evaluate(manifest)
            self.assertGreater(len(dossier.hypotheses), 1)
            before = _runtime_state(runtime, dossier)

            with self.assertRaisesRegex(ValidationError, "cover every hypothesis"):
                runtime.review(
                    dossier,
                    _review(
                        dossier,
                        review_id="review-partial-hypotheses",
                        hypothesis_ids=(dossier.hypotheses[0].hypothesis_id,),
                    ),
                )

            self.assertEqual(_runtime_state(runtime, dossier), before)

    def test_partial_accepted_review_is_atomic_and_retryable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            dossier = runtime.evaluate(fixture_manifest())
            self.assertGreater(len(dossier.evidence), 1)
            before = _runtime_state(runtime, dossier)
            partial = _review(
                dossier,
                review_id="review-partial-atomic",
                claim_ids=tuple(item.evidence_id for item in dossier.evidence[:-1]),
            )

            with self.assertRaisesRegex(ValidationError, "cover every evidence claim"):
                runtime.review(dossier, partial)

            self.assertEqual(_runtime_state(runtime, dossier), before)
            released = runtime.review(
                dossier,
                _review(dossier, review_id=partial.review_id),
            )
            self.assertIs(released.status, ResearchStatus.RELEASED_RESEARCH)
            self.assertTrue(released.is_releasable)

    def test_store_valid_but_unpersisted_forged_source_is_rejected_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            dossier = runtime.evaluate(fixture_manifest())
            forged = runtime._readdress(
                replace(dossier, warnings=(*dossier.warnings, "forged-current-snapshot"))
            )
            self.assertTrue(ContractValidator().validate_dossier(forged).valid)
            before = _runtime_state(runtime, dossier)

            with self.assertRaisesRegex(ValidationError, "current persisted run snapshot"):
                runtime.review(forged, _review(forged))

            self.assertEqual(_runtime_state(runtime, dossier), before)

    def test_failed_release_gate_does_not_advance_log_or_store(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            dossier = runtime.evaluate(fixture_manifest())
            before = _runtime_state(runtime, dossier)
            denied = ValidationReport(
                False,
                (
                    ValidationIssue(
                        "test_gate_denied",
                        IssueSeverity.ERROR,
                        "Synthetic release denial.",
                        "release",
                        "Keep the dossier unreleased.",
                    ),
                ),
            )

            with patch.object(ReleaseGate, "check", return_value=denied):
                with self.assertRaisesRegex(ValidationError, "test_gate_denied"):
                    runtime.review(dossier, _review(dossier, review_id="review-gate-denied"))

            self.assertEqual(_runtime_state(runtime, dossier), before)

    def test_review_commit_uses_atomic_current_pointer_advance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            dossier = runtime.evaluate(fixture_manifest())
            before = runtime.get_run(dossier.run_id)

            with patch.object(
                runtime.store,
                "advance_run",
                wraps=runtime.store.advance_run,
            ) as advance:
                released = runtime.review_run(dossier.run_id, _review(dossier))

            advance.assert_called_once()
            self.assertEqual(
                advance.call_args.kwargs["expected_run"],
                before,
            )
            self.assertEqual(
                runtime.get_run(dossier.run_id)["dossier_address"],
                released.content_address,
            )

    def test_two_runtime_release_race_has_one_closed_winner(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            seed = CaseRuntime(directory)
            dossier = seed.evaluate(fixture_manifest())
            initial = seed.get_run(dossier.run_id)
            runtimes = (CaseRuntime(directory), CaseRuntime(directory))
            reviews = (
                _review(dossier, review_id="review-race-left"),
                _review(dossier, review_id="review-race-right"),
            )
            barrier = threading.Barrier(2)
            results: Queue[tuple[str, CaseRuntime, object]] = Queue()

            def guarded_advance(original, *args: object, **kwargs: object) -> object:
                barrier.wait(timeout=10)
                return original(*args, **kwargs)

            def run_review(runtime: CaseRuntime, review: ReviewDecision) -> None:
                try:
                    results.put(("ok", runtime, runtime.review_run(dossier.run_id, review)))
                except BaseException as exc:  # pragma: no cover - asserted below
                    results.put(("error", runtime, exc))

            originals = tuple(runtime.store.advance_run for runtime in runtimes)
            with (
                patch.object(
                    runtimes[0].store,
                    "advance_run",
                    side_effect=lambda *args, **kwargs: guarded_advance(
                        originals[0], *args, **kwargs
                    ),
                ),
                patch.object(
                    runtimes[1].store,
                    "advance_run",
                    side_effect=lambda *args, **kwargs: guarded_advance(
                        originals[1], *args, **kwargs
                    ),
                ),
            ):
                threads = tuple(
                    threading.Thread(target=run_review, args=(runtime, review))
                    for runtime, review in zip(runtimes, reviews, strict=True)
                )
                for thread in threads:
                    thread.start()
                for thread in threads:
                    thread.join(timeout=15)

            self.assertFalse(any(thread.is_alive() for thread in threads))
            outcomes = [results.get(timeout=2) for _ in runtimes]
            winners = [item for item in outcomes if item[0] == "ok"]
            losers = [item for item in outcomes if item[0] == "error"]
            self.assertEqual(len(winners), 1, outcomes)
            self.assertEqual(len(losers), 1, outcomes)
            loser_error = cast(BaseException, losers[0][2])
            self.assertIsInstance(loser_error, ValidationError)
            self.assertIsInstance(loser_error.__cause__, StoreError)
            self.assertEqual(losers[0][1]._logs, {})

            winner = winners[0][2]
            self.assertIsInstance(winner, Dossier)
            current = seed.get_run(dossier.run_id)
            self.assertNotEqual(current["dossier_address"], initial["dossier_address"])
            self.assertEqual(len(current["dossier_history"]), 2)
            self.assertEqual(len(current["event_history"]), 2)
            current_dossier = seed.get_dossier(current["dossier_address"])
            current_events = seed.store.store.get(current["event_address"])["events"]
            winner_id = current_dossier["review"]["review_id"]
            self.assertIn(winner_id, {review.review_id for review in reviews})
            self.assertEqual(current_events[-1]["event_id"], winner_id)
            self.assertEqual(
                {event["event_id"] for event in current_events}
                & {review.review_id for review in reviews},
                {winner_id},
            )

    def test_stale_assignment_loses_cas_without_poisoning_cached_log(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            primary = CaseRuntime(directory)
            dossier = primary.evaluate(fixture_manifest())
            competitor = CaseRuntime(directory)
            before_cached = primary._logs[dossier.run_id].to_record()
            original_advance = primary.store.advance_run

            def advance_after_competitor(*args: object, **kwargs: object) -> object:
                competitor.assign_review(
                    dossier.run_id,
                    assignment_id="assignment-cas-winner",
                    reviewer="reviewer-winner",
                )
                return original_advance(*args, **kwargs)  # type: ignore[arg-type]

            with patch.object(
                primary.store,
                "advance_run",
                side_effect=advance_after_competitor,
            ):
                with self.assertRaisesRegex(ValidationError, "expected current state") as raised:
                    primary.assign_review(
                        dossier.run_id,
                        assignment_id="assignment-cas-loser",
                        reviewer="reviewer-loser",
                    )

            self.assertIsInstance(raised.exception.__cause__, StoreError)
            self.assertEqual(primary._logs[dossier.run_id].to_record(), before_cached)
            current = primary.get_run(dossier.run_id)
            current_events = primary.store.store.get(current["event_address"])["events"]
            current_ids = {item["event_id"] for item in current_events}
            self.assertIn("assignment-cas-winner", current_ids)
            self.assertNotIn("assignment-cas-loser", current_ids)

    def test_assignment_rejects_non_exact_strings_before_mutation(self) -> None:
        class StringSubclass(str):
            pass

        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            dossier = runtime.evaluate(fixture_manifest())
            before = _runtime_state(runtime, dossier)

            with self.assertRaisesRegex(ValidationError, "exact strings"):
                runtime.assign_review(
                    dossier.run_id,
                    assignment_id=StringSubclass("assignment-subclass"),
                    reviewer="reviewer",
                )

            self.assertEqual(_runtime_state(runtime, dossier), before)

    def test_assignment_response_binds_the_snapshot_that_won_publication(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            dossier = runtime.evaluate(fixture_manifest())
            original_get_run = runtime.get_run
            read_count = 0

            def simulate_immediate_later_advance(run_id: str):
                nonlocal read_count
                read_count += 1
                current = original_get_run(run_id)
                if read_count == 1:
                    return current
                return {**current, "event_address": f"sha256:{'0' * 64}"}

            with patch.object(runtime, "get_run", side_effect=simulate_immediate_later_advance):
                response = runtime.assign_review(
                    dossier.run_id,
                    assignment_id="assignment-response-snapshot",
                    reviewer="reviewer",
                )

            persisted = original_get_run(dossier.run_id)
            self.assertEqual(read_count, 1)
            self.assertEqual(response["event_address"], persisted["event_address"])
            self.assertEqual(
                runtime.store.store.get(response["event_address"])["events"][-1]["event_id"],
                "assignment-response-snapshot",
            )

    def test_is_releasable_matches_exhaustive_release_gate_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            dossier = runtime.evaluate(fixture_manifest())
            released = runtime.review(dossier, _review(dossier))
            self.assertTrue(released.is_releasable)
            self.assertTrue(ReleaseGate().check(released).valid)

            partial_review = _review(
                dossier,
                review_id="review-partial-summary",
                claim_ids=tuple(item.evidence_id for item in dossier.evidence[:-1]),
            )
            partial = runtime._readdress(replace(released, review=partial_review))
            self.assertFalse(partial.is_releasable)
            self.assertFalse(ReleaseGate().check(partial).valid)

    def test_rejected_and_returned_review_run_flows_remain_valid(self) -> None:
        for state in (ReviewState.REJECTED, ReviewState.RETURNED):
            with self.subTest(state=state.value), tempfile.TemporaryDirectory() as directory:
                runtime = CaseRuntime(directory)
                dossier = runtime.evaluate(fixture_manifest())
                reviewed = runtime.review_run(
                    dossier.run_id,
                    _review(
                        dossier,
                        state=state,
                        review_id=f"review-{state.value}",
                        hypothesis_ids=(dossier.hypotheses[0].hypothesis_id,),
                        claim_ids=(),
                    ),
                )

                self.assertIs(reviewed.status, ResearchStatus.REVIEWED)
                attached_review = reviewed.review
                self.assertIsNotNone(attached_review)
                assert attached_review is not None
                self.assertIs(attached_review.state, state)
                self.assertFalse(reviewed.is_releasable)
                self.assertTrue(ContractValidator().validate_dossier(reviewed).valid)
                self.assertEqual(
                    runtime.get_run(dossier.run_id)["dossier_address"],
                    reviewed.content_address,
                )

    def test_review_run_replay_failure_does_not_install_a_log(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            writer = CaseRuntime(directory)
            dossier = writer.evaluate(fixture_manifest())
            run_record = writer.get_run(dossier.run_id)
            dossier_path = (
                writer.store.store.objects
                / f"{run_record['dossier_address'].split(':', 1)[1]}.json"
            )
            stored = json.loads(dossier_path.read_text(encoding="utf-8"))
            stored["case_id"] = "forged-persisted-case"
            dossier_path.write_text(json.dumps(stored), encoding="utf-8")
            reader = CaseRuntime(directory)

            with self.assertRaises(ValidationError):
                reader.review_run(dossier.run_id, _review(dossier))

            self.assertEqual(reader._logs, {})
            self.assertEqual(reader.get_run(dossier.run_id), run_record)

    def test_tampered_input_object_blocks_review_without_installing_log(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            writer = CaseRuntime(directory)
            dossier = writer.evaluate(fixture_manifest())
            run_record = writer.get_run(dossier.run_id)
            run_path = writer.store.runs / f"{dossier.run_id}.json"
            before_run_bytes = run_path.read_bytes()
            input_path = (
                writer.store.store.objects / f"{run_record['input_address'].split(':', 1)[1]}.json"
            )
            input_record = json.loads(input_path.read_text(encoding="utf-8"))
            input_record["case_id"] = "tampered-input-case"
            input_path.write_text(json.dumps(input_record), encoding="utf-8")
            reader = CaseRuntime(directory)

            with self.assertRaisesRegex(ValidationError, "input"):
                reader.review_run(dossier.run_id, _review(dossier))

            self.assertEqual(reader._logs, {})
            self.assertEqual(run_path.read_bytes(), before_run_bytes)
            self.assertEqual(reader.get_run(dossier.run_id), run_record)

    def test_noncanonical_review_fails_before_any_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            dossier = runtime.evaluate(fixture_manifest())
            review = _review(dossier, review_id="review-forged-state")
            object.__setattr__(review, "state", "accepted")
            before = _runtime_state(runtime, dossier)

            with self.assertRaisesRegex(ValidationError, "exact ReviewState"):
                runtime.review(dossier, review)

            self.assertEqual(_runtime_state(runtime, dossier), before)

    def test_replaced_dependencies_and_mutated_reports_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            runtime.validator = object()  # type: ignore[assignment]
            with self.assertRaisesRegex(ValidationError, "exact ContractValidator"):
                runtime.evaluate(fixture_manifest())
            self.assertEqual(tuple(Path(directory).joinpath("runs").glob("*.json")), ())

        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            issue = ValidationIssue(
                "mutated_report",
                IssueSeverity.ERROR,
                "The report was mutated after construction.",
                "validation",
                "Reject the report.",
            )
            report = ValidationReport(False, (issue,))
            object.__setattr__(report, "valid", True)
            with self.assertRaisesRegex(ValidationError, "invalid validation report"):
                runtime._require_valid(report, "case manifest")

        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            manifest = fixture_manifest()
            object.__setattr__(manifest, "variants", list(manifest.variants))
            with patch.object(
                runtime.validator,
                "validate_manifest",
                return_value=ValidationReport(True, ()),
            ):
                with self.assertRaisesRegex(ValidationError, "non-canonical instance state"):
                    runtime.evaluate(manifest)
            self.assertEqual(tuple(runtime.store.runs.glob("*.json")), ())
            self.assertEqual(tuple(runtime.store.store.objects.glob("*.json")), ())

        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            dossier = runtime.evaluate(fixture_manifest())
            before = _runtime_state(runtime, dossier)
            with patch.object(
                runtime.release_gate,
                "check",
                return_value=ValidationReport(True, ()),
            ):
                with self.assertRaisesRegex(ValidationError, "non-canonical instance state"):
                    runtime.review(dossier, _review(dossier, review_id="review-shadowed-gate"))
            self.assertEqual(_runtime_state(runtime, dossier), before)

    def test_callback_cannot_replace_dependency_class_descriptors(self) -> None:
        manifest = fixture_manifest()
        reference_bundle = ReferenceBundle.create(
            variant_id=manifest.variants[0].variant_id,
            context=manifest.context,
            sequence=None,
            elements=(),
            raw_features=(),
            receipts=(),
            warnings=(),
        )
        cases = (
            (ExperimentPlanner, "plan_many"),
            (RunStore, "create_run"),
            (ObjectStore, "put"),
        )
        for target, attribute in cases:
            with self.subTest(target=target.__name__, attribute=attribute):
                original = vars(target)[attribute]

                class MutatingRetriever:
                    def __init__(self, dependency_class, method_name) -> None:
                        self.dependency_class = dependency_class
                        self.method_name = method_name

                    def enrich_manifest(self, value):
                        setattr(
                            self.dependency_class,
                            self.method_name,
                            lambda *_args, **_kwargs: None,
                        )
                        return EnrichmentResult(value, (reference_bundle,), ())

                try:
                    with tempfile.TemporaryDirectory() as directory:
                        runtime = CaseRuntime(
                            directory,
                            reference_retriever=MutatingRetriever(target, attribute),
                        )
                        with self.assertRaisesRegex(
                            ValidationError,
                            "runtime evaluation configuration changed",
                        ):
                            runtime.evaluate(manifest, live_reference=True)
                        self.assertIs(vars(target)[attribute], original)
                        self.assertEqual(tuple(runtime.store.runs.glob("*.json")), ())
                        self.assertEqual(
                            tuple(runtime.store.store.objects.glob("*.json")),
                            (),
                        )
                        self.assertEqual(runtime.evaluate(manifest).case_id, manifest.case_id)
                finally:
                    setattr(target, attribute, original)

    def test_callback_cannot_bypass_builder_and_validator_with_class_patches(self) -> None:
        manifest = fixture_manifest()
        reference_bundle = ReferenceBundle.create(
            variant_id=manifest.variants[0].variant_id,
            context=manifest.context,
            sequence=None,
            elements=(),
            raw_features=(),
            receipts=(),
            warnings=(),
        )
        original_build = vars(HypothesisBuilder)["build"]
        original_validate_dossier = vars(ContractValidator)["validate_dossier"]

        class MutatingRetriever:
            @staticmethod
            def enrich_manifest(value):
                HypothesisBuilder.build = lambda *_args, **_kwargs: None
                ContractValidator.validate_dossier = lambda *_args, **_kwargs: ValidationReport(
                    True,
                    (),
                )
                return EnrichmentResult(value, (reference_bundle,), ())

        try:
            with tempfile.TemporaryDirectory() as directory:
                runtime = CaseRuntime(
                    directory,
                    reference_retriever=MutatingRetriever(),
                )

                with self.assertRaisesRegex(
                    ValidationError,
                    "runtime evaluation configuration changed",
                ):
                    runtime.evaluate(manifest, live_reference=True)

                self.assertIs(vars(HypothesisBuilder)["build"], original_build)
                self.assertIs(
                    vars(ContractValidator)["validate_dossier"],
                    original_validate_dossier,
                )
                self.assertEqual(tuple(runtime.store.runs.glob("*.json")), ())
                self.assertEqual(tuple(runtime.store.store.objects.glob("*.json")), ())
                retry = runtime.evaluate(manifest)
                self.assertEqual(retry.case_id, manifest.case_id)
                self.assertTrue(ContractValidator().validate_dossier(retry).valid)
        finally:
            setattr(HypothesisBuilder, "build", original_build)  # noqa: B010
            setattr(  # noqa: B010
                ContractValidator,
                "validate_dossier",
                original_validate_dossier,
            )

    def test_callback_cannot_replace_runtime_guard_or_module_bindings(self) -> None:
        manifest = fixture_manifest()
        reference_bundle = ReferenceBundle.create(
            variant_id=manifest.variants[0].variant_id,
            context=manifest.context,
            sequence=None,
            elements=(),
            raw_features=(),
            receipts=(),
            warnings=(),
        )
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            captured = runtime._capture_evaluation_configuration()  # noqa: SLF001
            configuration_type = type(captured)
            class_snapshot_type = type(captured.dependency_class_namespaces[0])
            original_assert = vars(CaseRuntime)["_assert_evaluation_configuration"]
            original_restore = vars(CaseRuntime)["_restore_evaluation_configuration"]
            original_configuration_slot = vars(configuration_type)["runtime_module_namespace"]
            original_class_snapshot_slot = vars(class_snapshot_type)["attributes"]
            original_canonical_bytes = runtime_module.canonical_bytes

            class MutatingRetriever:
                @staticmethod
                def enrich_manifest(value):
                    CaseRuntime._assert_evaluation_configuration = lambda *_args, **_kwargs: None
                    CaseRuntime._restore_evaluation_configuration = lambda *_args, **_kwargs: False
                    configuration_type.runtime_module_namespace = property(lambda _value: None)
                    class_snapshot_type.attributes = property(lambda _value: ())
                    runtime_module.canonical_bytes = lambda *_args, **_kwargs: b"{}"
                    return EnrichmentResult(value, (reference_bundle,), ())

            runtime.reference_retriever = MutatingRetriever()
            try:
                with self.assertRaisesRegex(
                    ValidationError,
                    "runtime evaluation configuration changed",
                ):
                    runtime.evaluate(manifest, live_reference=True)

                self.assertIs(
                    vars(CaseRuntime)["_assert_evaluation_configuration"],
                    original_assert,
                )
                self.assertIs(
                    vars(CaseRuntime)["_restore_evaluation_configuration"],
                    original_restore,
                )
                self.assertIs(
                    vars(configuration_type)["runtime_module_namespace"],
                    original_configuration_slot,
                )
                self.assertIs(
                    vars(class_snapshot_type)["attributes"],
                    original_class_snapshot_slot,
                )
                self.assertIs(runtime_module.canonical_bytes, original_canonical_bytes)
                self.assertEqual(tuple(runtime.store.runs.glob("*.json")), ())
                self.assertEqual(tuple(runtime.store.store.objects.glob("*.json")), ())
                retry = runtime.evaluate(manifest)
                self.assertEqual(retry.case_id, manifest.case_id)
            finally:
                runtime_module.canonical_bytes = original_canonical_bytes
                setattr(  # noqa: B010
                    CaseRuntime,
                    "_assert_evaluation_configuration",
                    original_assert,
                )
                setattr(  # noqa: B010
                    CaseRuntime,
                    "_restore_evaluation_configuration",
                    original_restore,
                )
                setattr(  # noqa: B010
                    configuration_type,
                    "runtime_module_namespace",
                    original_configuration_slot,
                )
                setattr(  # noqa: B010
                    class_snapshot_type,
                    "attributes",
                    original_class_snapshot_slot,
                )

    def test_callback_cannot_mutate_guard_or_dependency_function_code_in_place(self) -> None:
        def replacement_scope_factory():
            retained_scope_state = object()

            def replacement_scope():
                _ = retained_scope_state
                yield

            return replacement_scope

        manifest = fixture_manifest()
        reference_bundle = ReferenceBundle.create(
            variant_id=manifest.variants[0].variant_id,
            context=manifest.context,
            sequence=None,
            elements=(),
            raw_features=(),
            receipts=(),
            warnings=(),
        )
        guard_function = vars(CaseRuntime)["_assert_evaluation_configuration"]
        builder_function = vars(HypothesisBuilder)["build"]
        canonical_function = runtime_module.canonical_bytes
        original_guard_code = guard_function.__code__
        original_builder_code = builder_function.__code__
        original_canonical_code = canonical_function.__code__
        runtime_scope = cast(Any, runtime_module.runtime_callback_scope)
        runtime_scope_dict = runtime_scope.__dict__
        runtime_scope_dict_items = tuple(runtime_scope_dict.items())
        runtime_scope_wrapped = runtime_scope.__wrapped__
        runtime_scope_wrapped_code = runtime_scope_wrapped.__code__
        isolation_error_type = callback_isolation_module.ValidationError
        replacement_scope = replacement_scope_factory()

        def no_op(*_args, **_kwargs):
            return None

        def false_canonical_bytes(*_args, **_kwargs):
            return b"{}"

        class MutatingRetriever:
            @staticmethod
            def enrich_manifest(value):
                result = EnrichmentResult(value, (reference_bundle,), ())
                guard_function.__code__ = no_op.__code__
                builder_function.__code__ = no_op.__code__
                canonical_function.__code__ = false_canonical_bytes.__code__
                runtime_scope.__dict__ = {"__wrapped__": replacement_scope}
                runtime_scope_wrapped.__code__ = replacement_scope.__code__
                vars(callback_isolation_module)["ValidationError"] = RuntimeError
                return result

        try:
            with tempfile.TemporaryDirectory() as directory:
                runtime = CaseRuntime(
                    directory,
                    reference_retriever=MutatingRetriever(),
                )

                with self.assertRaisesRegex(
                    ValidationError,
                    "runtime evaluation configuration changed",
                ):
                    runtime.evaluate(manifest, live_reference=True)

                self.assertIs(guard_function.__code__, original_guard_code)
                self.assertIs(builder_function.__code__, original_builder_code)
                self.assertIs(canonical_function.__code__, original_canonical_code)
                self.assertIs(runtime_scope.__dict__, runtime_scope_dict)
                self.assertIs(runtime_scope.__wrapped__, runtime_scope_wrapped)
                self.assertIs(runtime_scope_wrapped.__code__, runtime_scope_wrapped_code)
                self.assertIs(callback_isolation_module.ValidationError, isolation_error_type)
                self.assertEqual(tuple(runtime.store.runs.glob("*.json")), ())
                self.assertEqual(tuple(runtime.store.store.objects.glob("*.json")), ())
                retry = runtime.evaluate(manifest)
                self.assertEqual(retry.case_id, manifest.case_id)
        finally:
            guard_function.__code__ = original_guard_code
            builder_function.__code__ = original_builder_code
            canonical_function.__code__ = original_canonical_code
            runtime_scope.__dict__ = runtime_scope_dict
            runtime_scope_dict.clear()
            runtime_scope_dict.update(dict(runtime_scope_dict_items))
            runtime_scope_wrapped.__code__ = runtime_scope_wrapped_code
            vars(callback_isolation_module)["ValidationError"] = isolation_error_type

    def test_callback_module_global_shadows_cannot_disable_runtime_recovery(self) -> None:
        manifest = fixture_manifest()
        reference_bundle = ReferenceBundle.create(
            variant_id=manifest.variants[0].variant_id,
            context=manifest.context,
            sequence=None,
            elements=(),
            raw_features=(),
            receipts=(),
            warnings=(),
        )
        runtime_namespace = vars(runtime_module)
        missing = object()
        poisoned_names = (
            "BaseException",
            "Exception",
            "all",
            "any",
            "cast",
            "CaseRuntime",
            "delattr",
            "detached_callback_guard",
            "dict",
            "fields",
            "getattr",
            "globals",
            "isfinite",
            "len",
            "max",
            "monotonic",
            "object",
            "set",
            "setattr",
            "type",
            "ValidationError",
            "vars",
            "zip",
        )
        originals = {
            name: runtime_namespace.get(name, missing)
            for name in poisoned_names
        }

        class MutatingRetriever:
            @staticmethod
            def enrich_manifest(value):
                result = EnrichmentResult(value, (reference_bundle,), ())
                runtime_namespace.update(dict.fromkeys(poisoned_names))
                return result

        try:
            with tempfile.TemporaryDirectory() as directory:
                runtime = CaseRuntime(
                    directory,
                    reference_retriever=MutatingRetriever(),
                )
                with self.assertRaisesRegex(
                    ValidationError,
                    "runtime evaluation configuration changed",
                ):
                    runtime.evaluate(manifest, live_reference=True)

                for name, original in originals.items():
                    with self.subTest(name=name):
                        if original is missing:
                            self.assertNotIn(name, runtime_namespace)
                        else:
                            self.assertIs(runtime_namespace[name], original)
                self.assertEqual(tuple(runtime.store.runs.glob("*.json")), ())
                self.assertEqual(tuple(runtime.store.store.objects.glob("*.json")), ())
                self.assertEqual(runtime.evaluate(manifest).case_id, manifest.case_id)
        finally:
            for name, original in originals.items():
                if original is missing:
                    runtime_namespace.pop(name, None)
                else:
                    runtime_namespace[name] = original

    def test_callback_cannot_mutate_a_transitively_discovered_class_method(self) -> None:
        manifest = fixture_manifest()
        reference_bundle = ReferenceBundle.create(
            variant_id=manifest.variants[0].variant_id,
            context=manifest.context,
            sequence=None,
            elements=(),
            raw_features=(),
            receipts=(),
            warnings=(),
        )
        context_to_dict = vars(context_module.ContextMatch)["to_dict"]
        original_code = context_to_dict.__code__

        def poisoned_to_dict(_self):
            return {"poisoned": True}

        class MutatingRetriever:
            @staticmethod
            def enrich_manifest(value):
                result = EnrichmentResult(value, (reference_bundle,), ())
                context_to_dict.__code__ = poisoned_to_dict.__code__
                return result

        try:
            with tempfile.TemporaryDirectory() as directory:
                runtime = CaseRuntime(
                    directory,
                    reference_retriever=MutatingRetriever(),
                )
                with self.assertRaisesRegex(
                    ValidationError,
                    "runtime evaluation configuration changed",
                ):
                    runtime.evaluate(manifest, live_reference=True)

                self.assertIs(context_to_dict.__code__, original_code)
                self.assertEqual(tuple(runtime.store.runs.glob("*.json")), ())
                self.assertEqual(tuple(runtime.store.store.objects.glob("*.json")), ())
                self.assertEqual(runtime.evaluate(manifest).case_id, manifest.case_id)
        finally:
            context_to_dict.__code__ = original_code

    def test_callback_cannot_shadow_runtime_methods_on_the_instance(self) -> None:
        manifest = fixture_manifest()
        reference_bundle = ReferenceBundle.create(
            variant_id=manifest.variants[0].variant_id,
            context=manifest.context,
            sequence=None,
            elements=(),
            raw_features=(),
            receipts=(),
            warnings=(),
        )
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)

            class MutatingRetriever:
                @staticmethod
                def enrich_manifest(value):
                    vars(runtime)["_validate_event_payload_size"] = lambda *_args, **_kwargs: None
                    return EnrichmentResult(value, (reference_bundle,), ())

            runtime.reference_retriever = MutatingRetriever()
            with self.assertRaisesRegex(
                ValidationError,
                "runtime evaluation configuration changed",
            ):
                runtime.evaluate(manifest, live_reference=True)

            self.assertNotIn("_validate_event_payload_size", vars(runtime))
            self.assertEqual(tuple(runtime.store.runs.glob("*.json")), ())
            self.assertEqual(tuple(runtime.store.store.objects.glob("*.json")), ())
            retry = runtime.evaluate(manifest)
            self.assertEqual(retry.case_id, manifest.case_id)

    def test_callback_cannot_replace_protected_function_dependency_module_globals(
        self,
    ) -> None:
        manifest = fixture_manifest()
        reference_bundle = ReferenceBundle.create(
            variant_id=manifest.variants[0].variant_id,
            context=manifest.context,
            sequence=None,
            elements=(),
            raw_features=(),
            receipts=(),
            warnings=(),
        )
        original_edge_type = hypotheses_module.HypothesisEdge

        class MutatingRetriever:
            @staticmethod
            def enrich_manifest(value):
                result = EnrichmentResult(value, (reference_bundle,), ())
                hypotheses_module.HypothesisEdge = object
                return result

        try:
            with tempfile.TemporaryDirectory() as directory:
                runtime = CaseRuntime(
                    directory,
                    reference_retriever=MutatingRetriever(),
                )
                with self.assertRaisesRegex(
                    ValidationError,
                    "runtime evaluation configuration changed",
                ):
                    runtime.evaluate(manifest, live_reference=True)

                self.assertIs(hypotheses_module.HypothesisEdge, original_edge_type)
                self.assertEqual(tuple(runtime.store.runs.glob("*.json")), ())
                self.assertEqual(tuple(runtime.store.store.objects.glob("*.json")), ())
                retry = runtime.evaluate(manifest)
                self.assertEqual(retry.case_id, manifest.case_id)
        finally:
            hypotheses_module.HypothesisEdge = original_edge_type

    def test_callback_cannot_mutate_builtin_retriever_configuration(self) -> None:
        manifest = fixture_manifest()
        reference_bundle = ReferenceBundle.create(
            variant_id=manifest.variants[0].variant_id,
            context=manifest.context,
            sequence=None,
            elements=(),
            raw_features=(),
            receipts=(),
            warnings=(),
        )
        atlas = PublicAtlasRetriever(
            track_adapters=ReferenceTrackAdapterRegistry(),
        )
        original_motifs = vars(atlas)["_motifs"]
        sequence_inference = vars(atlas)["_sequence_inference"]
        scanner = vars(sequence_inference)["scanner"]
        track_registry = vars(atlas)["_track_adapters"]
        track_entries = vars(track_registry)["_adapters"]
        original_analyze = vars(SequenceInference)["analyze"]
        iupac = vars(sequence_inference_module)["_IUPAC"]
        original_iupac = dict(iupac)

        class MutatingRetriever:
            @staticmethod
            def enrich_manifest(value):
                vars(atlas)["_motifs"] = ("forged-motif-configuration",)
                vars(scanner)["forged_configuration"] = True
                track_entries["forged-adapter"] = object()
                SequenceInference.analyze = lambda *_args, **_kwargs: object()
                iupac["A"] = frozenset("T")
                return EnrichmentResult(value, (reference_bundle,), ())

        try:
            with tempfile.TemporaryDirectory() as directory:
                runtime = CaseRuntime(
                    directory,
                    reference_retriever=MutatingRetriever(),
                    atlas_retriever=atlas,
                )

                with self.assertRaisesRegex(
                    ValidationError,
                    "runtime evaluation configuration changed",
                ):
                    runtime.evaluate(manifest, live_reference=True)

                self.assertIs(vars(atlas)["_motifs"], original_motifs)
                self.assertEqual(vars(scanner), {})
                self.assertEqual(track_entries, {})
                self.assertIs(vars(SequenceInference)["analyze"], original_analyze)
                self.assertEqual(iupac, original_iupac)
                self.assertEqual(tuple(runtime.store.runs.glob("*.json")), ())
                self.assertEqual(tuple(runtime.store.store.objects.glob("*.json")), ())
                retry = runtime.evaluate(manifest)
                self.assertEqual(retry.case_id, manifest.case_id)
        finally:
            setattr(SequenceInference, "analyze", original_analyze)  # noqa: B010
            iupac.clear()
            iupac.update(original_iupac)

    def test_semantic_module_mapping_inventory_is_explicit_and_excludes_caches(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            snapshot = runtime._capture_evaluation_configuration()  # noqa: SLF001

        protected_targets = {
            id(mapping.target)
            for module_state in snapshot.dependency_module_namespaces
            for mapping in module_state.mapping_states
        }
        expected_targets = {
            id(vars(context_module)["_WEIGHTS"]),
            id(vars(expression_claims_module)["_STATE_MAP"]),
            id(vars(policy_module)["_CONFUSABLE_ASCII"]),
            id(vars(sequence_inference_module)["_IUPAC"]),
        }
        self.assertEqual(protected_targets, expected_targets)
        self.assertNotIn(id(vars(data_sources_module)["_CACHE_LOCKS"]), protected_targets)
        self.assertNotIn(id(vars(storage_module)["_RUN_LOCKS"]), protected_targets)
        protected_class_targets = {
            id(mapping.target)
            for class_state in snapshot.dependency_class_namespaces
            for mapping in class_state.mapping_states
        }
        self.assertIn(id(vars(CaseManifest)["__dataclass_fields__"]), protected_class_targets)
        self.assertIn(
            id(vars(data_sources_module.UcscRestClient)["_assemblies"]),
            protected_class_targets,
        )

    def test_callback_cannot_mutate_semantic_dependency_mappings_in_place(self) -> None:
        manifest = fixture_manifest()
        reference_bundle = ReferenceBundle.create(
            variant_id=manifest.variants[0].variant_id,
            context=manifest.context,
            sequence=None,
            elements=(),
            raw_features=(),
            receipts=(),
            warnings=(),
        )
        cases = (
            (
                "context weights",
                vars(context_module)["_WEIGHTS"],
                "genome_build",
                0.01,
            ),
            (
                "RNA claim state map",
                vars(expression_claims_module)["_STATE_MAP"],
                RNAEvidenceState.SUPPORTED,
                EvidenceState.CONTRADICTORY,
            ),
            (
                "policy confusable map",
                vars(policy_module)["_CONFUSABLE_ASCII"],
                1040,
                "Z",
            ),
            (
                "sequence IUPAC map",
                vars(sequence_inference_module)["_IUPAC"],
                "A",
                frozenset("T"),
            ),
        )
        for label, mapping, key, forged_value in cases:
            with self.subTest(label=label):
                original = dict(mapping)

                class MutatingRetriever:
                    @staticmethod
                    def enrich_manifest(
                        value,
                        selected_mapping=mapping,
                        selected_key=key,
                        selected_value=forged_value,
                    ):
                        selected_mapping[selected_key] = selected_value
                        return EnrichmentResult(value, (reference_bundle,), ())

                try:
                    with tempfile.TemporaryDirectory() as directory:
                        runtime = CaseRuntime(
                            directory,
                            reference_retriever=MutatingRetriever(),
                        )
                        with self.assertRaisesRegex(
                            ValidationError,
                            "runtime evaluation configuration changed",
                        ):
                            runtime.evaluate(manifest, live_reference=True)

                        self.assertEqual(mapping, original)
                        self.assertEqual(tuple(runtime.store.runs.glob("*.json")), ())
                        self.assertEqual(tuple(runtime.store.store.objects.glob("*.json")), ())
                        retry = runtime.evaluate(manifest)
                        self.assertEqual(retry.case_id, manifest.case_id)
                finally:
                    mapping.clear()
                    mapping.update(original)

    def test_callback_cannot_mutate_semantic_class_mappings_in_place(self) -> None:
        manifest = fixture_manifest()
        reference_bundle = ReferenceBundle.create(
            variant_id=manifest.variants[0].variant_id,
            context=manifest.context,
            sequence=None,
            elements=(),
            raw_features=(),
            receipts=(),
            warnings=(),
        )
        cases = (
            (
                "dataclass field registry",
                vars(CaseManifest)["__dataclass_fields__"],
                None,
                None,
            ),
            (
                "UCSC assemblies",
                vars(data_sources_module.UcscRestClient)["_assemblies"],
                "GRCh38",
                "hg19",
            ),
        )
        for label, mapping, key, forged_value in cases:
            with self.subTest(label=label):
                original = dict(mapping)

                class MutatingRetriever:
                    @staticmethod
                    def enrich_manifest(
                        value,
                        selected_mapping=mapping,
                        selected_key=key,
                        selected_value=forged_value,
                    ):
                        result = EnrichmentResult(value, (reference_bundle,), ())
                        if selected_key is None:
                            selected_mapping.clear()
                        else:
                            selected_mapping[selected_key] = selected_value
                        return result

                try:
                    with tempfile.TemporaryDirectory() as directory:
                        runtime = CaseRuntime(
                            directory,
                            reference_retriever=MutatingRetriever(),
                        )
                        with self.assertRaisesRegex(
                            ValidationError,
                            "runtime evaluation configuration changed",
                        ):
                            runtime.evaluate(manifest, live_reference=True)

                        self.assertEqual(mapping, original)
                        self.assertEqual(tuple(runtime.store.runs.glob("*.json")), ())
                        self.assertEqual(tuple(runtime.store.store.objects.glob("*.json")), ())
                        retry = runtime.evaluate(manifest)
                        self.assertEqual(retry.case_id, manifest.case_id)
                finally:
                    mapping.clear()
                    mapping.update(original)

        field = vars(CaseManifest)["__dataclass_fields__"]["case_id"]
        original_field_name = field.name

        class MutatingFieldRetriever:
            @staticmethod
            def enrich_manifest(value):
                result = EnrichmentResult(value, (reference_bundle,), ())
                field.name = "forged_case_id"
                return result

        try:
            with tempfile.TemporaryDirectory() as directory:
                runtime = CaseRuntime(
                    directory,
                    reference_retriever=MutatingFieldRetriever(),
                )
                with self.assertRaisesRegex(
                    ValidationError,
                    "runtime evaluation configuration changed",
                ):
                    runtime.evaluate(manifest, live_reference=True)

                self.assertEqual(field.name, original_field_name)
                self.assertEqual(tuple(runtime.store.runs.glob("*.json")), ())
                self.assertEqual(tuple(runtime.store.store.objects.glob("*.json")), ())
                retry = runtime.evaluate(manifest)
                self.assertEqual(retry.case_id, manifest.case_id)
        finally:
            field.name = original_field_name

    def test_callback_cannot_mutate_declared_track_adapter_metadata_in_place(self) -> None:
        manifest = fixture_manifest()
        variant = manifest.variants[0]
        metadata = ReferenceTrackMetadata(
            adapter_id="runtime-guard-track",
            display_name="Runtime guard track",
            version="2026.09",
            assembly=manifest.context.genome_build,
            track_type="open_chromatin",
            source_id="SRC-RUNTIME-GUARD-TRACK",
            source_version="fixture-1",
            license="CC-BY-4.0",
            access_mode=ReferenceAccessMode.LOCAL_CACHE,
            uri="urn:glio:track:runtime-guard-track:2026.09",
            coordinate_system=CoordinateSystem.ONE_BASED_INCLUSIVE,
            supported_contexts=(manifest.context.key,),
            channels=("accessibility",),
            limitations=("Reference overlap is not evidence of causality.",),
        )
        built = DeclaredReferenceTrackAdapter.from_rows(
            metadata,
            (
                {
                    "record_id": "runtime-guard-row",
                    "chromosome": variant.chromosome,
                    "start": variant.start,
                    "end": variant.end,
                    "context_key": manifest.context.key,
                    "payload": {"signal": 0.75},
                },
            ),
        )
        self.assertTrue(built.accepted, built.to_dict())
        atlas = PublicAtlasRetriever(
            track_adapters=ReferenceTrackAdapterRegistry((built.adapter,)),
        )
        track_registry = vars(atlas)["_track_adapters"]
        internal_adapter = vars(track_registry)["_adapters"][metadata.adapter_id]
        original_record = internal_adapter.to_dict()
        reference_bundle = ReferenceBundle.create(
            variant_id=variant.variant_id,
            context=manifest.context,
            sequence=None,
            elements=(),
            raw_features=(),
            receipts=(),
            warnings=(),
        )

        class MutatingRetriever:
            @staticmethod
            def enrich_manifest(value):
                object.__setattr__(
                    internal_adapter.metadata,
                    "limitations",
                    ("MUTATED DURING CALLBACK",),
                )
                return EnrichmentResult(value, (reference_bundle,), ())

        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(
                directory,
                reference_retriever=MutatingRetriever(),
                atlas_retriever=atlas,
            )
            with self.assertRaisesRegex(
                ValidationError,
                "runtime evaluation configuration changed",
            ):
                runtime.evaluate(manifest, live_reference=True)

            self.assertEqual(internal_adapter.to_dict(), original_record)
            self.assertEqual(tuple(runtime.store.runs.glob("*.json")), ())
            self.assertEqual(tuple(runtime.store.store.objects.glob("*.json")), ())
            retry = runtime.evaluate(manifest)
            self.assertEqual(retry.case_id, manifest.case_id)

    def test_callback_cannot_mutate_public_source_configuration_in_place(self) -> None:
        manifest = fixture_manifest()
        reference_bundle = ReferenceBundle.create(
            variant_id=manifest.variants[0].variant_id,
            context=manifest.context,
            sequence=None,
            elements=(),
            raw_features=(),
            receipts=(),
            warnings=(),
        )
        with tempfile.TemporaryDirectory() as directory:
            cache_root = Path(directory) / "source-cache"
            retriever = PublicReferenceRetriever(
                cache_root=cache_root,
                limits=ReferenceRetrievalLimits(),
            )
            client = retriever.client
            transport = cast(UrllibTransport, client.transport)
            retry_policy = client.retry_policy
            cache = client.cache
            specs = vars(client.catalog)["_specs"]
            ensembl_spec = specs["SRC-ENSEMBL-REST"]
            limiter = vars(client)["_limiters"]["SRC-ENSEMBL-REST"]
            assemblies = vars(type(retriever.ucsc))["_assemblies"]
            original_assemblies = dict(assemblies)
            original_limits = ReferenceRetrievalLimits()
            original_timeout = client.timeout_seconds
            original_transport_limit = transport.max_response_bytes
            original_retry = RetryPolicy(
                attempts=retry_policy.attempts,
                initial_backoff_seconds=retry_policy.initial_backoff_seconds,
                maximum_backoff_seconds=retry_policy.maximum_backoff_seconds,
                retry_statuses=retry_policy.retry_statuses,
            )
            original_region_limit = ensembl_spec.max_region_bp
            original_interval = limiter.interval_seconds
            original_cache_root = cache.root
            original_cache_locks = cache._locks  # noqa: SLF001

            def mutate_and_enrich(_retriever, value):
                object.__setattr__(
                    retriever.limits,
                    "max_total_canonical_bytes",
                    retriever.limits.max_total_canonical_bytes - 1,
                )
                object.__setattr__(
                    retriever.limits,
                    "max_total_sequence_bp",
                    retriever.limits.max_total_sequence_bp - 1,
                )
                client.timeout_seconds = original_timeout / 2
                transport.max_response_bytes = original_transport_limit - 1
                object.__setattr__(retry_policy, "attempts", 2)
                object.__setattr__(
                    ensembl_spec,
                    "max_region_bp",
                    cast(int, original_region_limit) - 1,
                )
                limiter.interval_seconds = original_interval + 0.25
                cache.root = Path(directory) / "forged-cache"
                cache._locks = cache.root / ".locks"  # noqa: SLF001
                assemblies["GRCh38"] = "hg19"
                return EnrichmentResult(value, (reference_bundle,), ())

            try:
                runtime = CaseRuntime(directory, reference_retriever=retriever)
                configuration = runtime._capture_evaluation_configuration()  # noqa: SLF001
                source_configuration = configuration.reference_source_configuration
                self.assertIsNotNone(source_configuration)
                assert source_configuration is not None
                limits_state = next(
                    item
                    for item in source_configuration.frozen_configurations
                    if item.target is retriever.limits
                )
                self.assertEqual(
                    tuple(name for name, _value in limits_state.attributes),
                    (
                        "max_window_bp",
                        "max_features_per_variant",
                        "max_variants",
                        "max_total_elements",
                        "max_total_canonical_bytes",
                        "max_total_sequence_bp",
                    ),
                )
                self.assertEqual(
                    {id(item.target) for item in source_configuration.mappings},
                    {
                        id(specs),
                        id(vars(client)["_limiters"]),
                        id(assemblies),
                    },
                )
                with patch.object(
                    PublicReferenceRetriever,
                    "enrich_manifest",
                    autospec=True,
                    side_effect=mutate_and_enrich,
                ):
                    with self.assertRaisesRegex(
                        ValidationError,
                        "runtime evaluation configuration changed",
                    ):
                        runtime.evaluate(manifest, live_reference=True)

                self.assertEqual(retriever.limits, original_limits)
                self.assertEqual(client.timeout_seconds, original_timeout)
                self.assertEqual(transport.max_response_bytes, original_transport_limit)
                self.assertEqual(retry_policy, original_retry)
                self.assertEqual(ensembl_spec.max_region_bp, original_region_limit)
                self.assertEqual(limiter.interval_seconds, original_interval)
                self.assertEqual(cache.root, original_cache_root)
                self.assertEqual(cache._locks, original_cache_locks)  # noqa: SLF001
                self.assertEqual(assemblies, original_assemblies)
                self.assertEqual(tuple(runtime.store.runs.glob("*.json")), ())
                self.assertEqual(tuple(runtime.store.store.objects.glob("*.json")), ())
                retry = runtime.evaluate(manifest)
                self.assertEqual(retry.case_id, manifest.case_id)
            finally:
                assemblies.clear()
                assemblies.update(original_assemblies)

    def test_failed_live_evaluation_does_not_rewind_source_rate_limiters(self) -> None:
        manifest = fixture_manifest()
        variant = manifest.variants[0]
        query_start = max(1, variant.start - 10)
        query_end = variant.end + 10
        sequence_url = (
            "https://api.genome.ucsc.edu/getData/sequence?chrom=chr7"
            f"&end={query_end}&genome=hg38&start={query_start - 1}"
        )
        overlap_url = (
            "https://rest.ensembl.org/overlap/region/homo_sapiens/"
            f"7:{query_start}-{query_end}?feature=gene&feature=motif&feature=regulatory"
        )
        responses: dict[str, object] = {
            sequence_url: {"dna": "A" * (query_end - query_start + 1)},
            overlap_url: [],
        }
        original_enrich = PublicReferenceRetriever.enrich_manifest

        class RecordingTransport:
            def __init__(self) -> None:
                self.calls: list[str] = []

            def request(
                self,
                method: str,
                url: str,
                headers: dict[str, str],
                timeout_seconds: float,
            ) -> TransportResponse:
                del method, headers, timeout_seconds
                self.calls.append(url)
                return TransportResponse(
                    200,
                    url,
                    {"content-type": "application/json"},
                    json.dumps(responses[url]).encode("utf-8"),
                    0.001,
                )

        for corruption in (None, 0.0, math.nan, -math.inf, math.inf, 1e308):
            with self.subTest(corruption=corruption), tempfile.TemporaryDirectory() as directory:
                transport = RecordingTransport()
                client = SourceClient(
                    cache_root=Path(directory) / "source-cache",
                    transport=transport,
                )
                retriever = PublicReferenceRetriever(
                    client,
                    window_bp=10,
                )
                runtime = CaseRuntime(directory, reference_retriever=retriever)
                original_planner = runtime.planner
                limiters = vars(client)["_limiters"]
                selected_limiters = {
                    source_id: limiters[source_id]
                    for source_id in ("SRC-UCSC-REST", "SRC-ENSEMBL-REST")
                }
                if corruption is not None:
                    object.__setattr__(
                        selected_limiters["SRC-ENSEMBL-REST"],
                        "_next_allowed",
                        1.0,
                    )
                before = {
                    source_id: object.__getattribute__(limiter, "_next_allowed")
                    for source_id, limiter in selected_limiters.items()
                }

                def enrich_then_invalidate(
                    selected_retriever,
                    value,
                    selected_corruption=corruption,
                    source_limiters=selected_limiters,
                    selected_runtime=runtime,
                ):
                    result = original_enrich(selected_retriever, value)
                    if selected_corruption is not None:
                        object.__setattr__(
                            source_limiters["SRC-ENSEMBL-REST"],
                            "_next_allowed",
                            selected_corruption,
                        )
                    selected_runtime.planner = ExperimentPlanner()
                    return result

                with patch.object(
                    PublicReferenceRetriever,
                    "enrich_manifest",
                    autospec=True,
                    side_effect=enrich_then_invalidate,
                ):
                    with self.assertRaisesRegex(
                        ValidationError,
                        "runtime evaluation configuration changed",
                    ):
                        runtime.evaluate(manifest, live_reference=True)

                after = {
                    source_id: object.__getattribute__(limiter, "_next_allowed")
                    for source_id, limiter in selected_limiters.items()
                }
                self.assertEqual(transport.calls, [sequence_url, overlap_url])
                self.assertGreater(
                    after["SRC-UCSC-REST"],
                    before["SRC-UCSC-REST"],
                )
                if corruption is None:
                    self.assertGreater(
                        after["SRC-ENSEMBL-REST"],
                        before["SRC-ENSEMBL-REST"],
                    )
                else:
                    self.assertEqual(
                        after["SRC-ENSEMBL-REST"],
                        before["SRC-ENSEMBL-REST"],
                    )
                self.assertIs(runtime.planner, original_planner)
                self.assertEqual(tuple(runtime.store.runs.glob("*.json")), ())
                self.assertEqual(tuple(runtime.store.store.objects.glob("*.json")), ())
                self.assertEqual(runtime.evaluate(manifest).case_id, manifest.case_id)

        with (
            self.subTest(corruption="preexisting-impossible"),
            tempfile.TemporaryDirectory() as directory,
        ):
            transport = RecordingTransport()
            client = SourceClient(
                cache_root=Path(directory) / "source-cache",
                transport=transport,
            )
            retriever = PublicReferenceRetriever(client, window_bp=10)
            runtime = CaseRuntime(directory, reference_retriever=retriever)
            limiter = vars(client)["_limiters"]["SRC-ENSEMBL-REST"]
            for impossible in (math.nan, -math.inf, math.inf, 1e308):
                object.__setattr__(limiter, "_next_allowed", impossible)
                with self.assertRaisesRegex(
                    ValidationError,
                    "rate limiter configuration is invalid",
                ):
                    runtime.evaluate(manifest)
            self.assertEqual(transport.calls, [])
            self.assertEqual(tuple(runtime.store.runs.glob("*.json")), ())
            self.assertEqual(tuple(runtime.store.store.objects.glob("*.json")), ())
            object.__setattr__(limiter, "_next_allowed", 0.0)
            self.assertEqual(runtime.evaluate(manifest).case_id, manifest.case_id)

    def test_permissive_policy_replacement_fails_before_persistence(self) -> None:
        class PermissivePolicy:
            version = "research-boundary-2026.09"

            @staticmethod
            def inspect_texts(texts: object) -> object:
                return object()

        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            runtime.policy = PermissivePolicy()  # type: ignore[assignment]

            with self.assertRaisesRegex(ValidationError, "exact ResearchPolicy"):
                runtime.evaluate(fixture_manifest())

            self.assertEqual(runtime._logs, {})
            self.assertEqual(tuple(runtime.store.runs.glob("*.json")), ())
            self.assertEqual(tuple(runtime.store.store.objects.glob("*.json")), ())

        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            object.__setattr__(runtime.policy, "version", "forged-policy-version")
            with self.assertRaisesRegex(ValidationError, "non-canonical instance state"):
                runtime.evaluate(fixture_manifest())
            self.assertEqual(tuple(runtime.store.runs.glob("*.json")), ())

        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            decision = runtime.policy.inspect_texts(("safe research text",))
            object.__setattr__(decision, "_integrity", "forged-integrity")
            with patch.object(ResearchPolicy, "inspect_texts", return_value=decision):
                with self.assertRaisesRegex(ValidationError, "invalid policy decision"):
                    runtime.evaluate(fixture_manifest())
            self.assertEqual(tuple(runtime.store.runs.glob("*.json")), ())

    def test_noncanonical_manifest_fails_before_runtime_persistence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            manifest = fixture_manifest()
            object.__setattr__(manifest, "variants", list(manifest.variants))

            with self.assertRaises(ValidationError):
                runtime.evaluate(manifest)

            self.assertEqual(runtime._logs, {})
            self.assertEqual(tuple(runtime.store.runs.glob("*.json")), ())
            self.assertEqual(tuple(runtime.store.store.objects.glob("*.json")), ())

    def test_live_reference_requires_an_exact_boolean_before_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)

            with self.assertRaisesRegex(ValidationError, "exact boolean"):
                runtime.evaluate(fixture_manifest(), live_reference=1)  # type: ignore[arg-type]

            self.assertEqual(runtime._logs, {})
            self.assertEqual(tuple(runtime.store.runs.glob("*.json")), ())
            self.assertEqual(tuple(runtime.store.store.objects.glob("*.json")), ())

    def test_repeated_untouched_offline_evaluate_reuses_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            writer = CaseRuntime(directory)
            original = writer.evaluate(fixture_manifest())
            run_path = writer.store.runs / f"{original.run_id}.json"
            run_bytes = run_path.read_bytes()
            objects = {
                path.name: path.read_bytes() for path in writer.store.store.objects.glob("*.json")
            }
            run_record = writer.get_run(original.run_id)
            reader = CaseRuntime(directory)

            with (
                patch.object(
                    ObjectStore,
                    "put",
                    autospec=True,
                    wraps=ObjectStore.put,
                ) as put,
                patch.object(
                    ObjectStore,
                    "put_at",
                    autospec=True,
                    wraps=ObjectStore.put_at,
                ) as put_at,
                patch.object(
                    RunStore,
                    "create_run",
                    autospec=True,
                    wraps=RunStore.create_run,
                ) as create_run,
            ):
                reused = reader.evaluate(fixture_manifest())

            put.assert_not_called()
            put_at.assert_not_called()
            create_run.assert_not_called()
            self.assertIsNot(reused, original)
            self.assertEqual(reused.to_dict(), original.to_dict())
            self.assertEqual(run_path.read_bytes(), run_bytes)
            self.assertEqual(
                {
                    path.name: path.read_bytes()
                    for path in writer.store.store.objects.glob("*.json")
                },
                objects,
            )
            self.assertEqual(run_record["event_history"], [run_record["event_address"]])
            self.assertEqual(run_record["dossier_history"], [run_record["dossier_address"]])
            self.assertEqual(
                reader._logs[original.run_id].to_record(),
                reader.store.store.get(run_record["event_address"]),
            )

    def test_repeated_offline_evaluate_rejects_different_output_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            writer = CaseRuntime(directory)
            original = writer.evaluate(fixture_manifest())
            self.assertGreater(len(original.experiments), 1)
            run_path = writer.store.runs / f"{original.run_id}.json"
            run_bytes = run_path.read_bytes()
            objects = {
                path.name: path.read_bytes() for path in writer.store.store.objects.glob("*.json")
            }
            retry = CaseRuntime(directory)

            with (
                patch.object(
                    ExperimentPlanner,
                    "plan_many",
                    autospec=True,
                    return_value=original.experiments[:-1],
                ),
                patch.object(
                    ObjectStore,
                    "put",
                    autospec=True,
                    wraps=ObjectStore.put,
                ) as put,
                patch.object(
                    RunStore,
                    "create_run",
                    autospec=True,
                    wraps=RunStore.create_run,
                ) as create_run,
            ):
                with self.assertRaisesRegex(ValidationError, "run already exists") as raised:
                    retry.evaluate(fixture_manifest())

            put.assert_not_called()
            create_run.assert_not_called()
            self.assertIsInstance(raised.exception.__cause__, StoreError)
            self.assertEqual(retry._logs, {})
            self.assertEqual(run_path.read_bytes(), run_bytes)
            self.assertEqual(
                {
                    path.name: path.read_bytes()
                    for path in writer.store.store.objects.glob("*.json")
                },
                objects,
            )

    def test_repeated_offline_evaluate_rejects_corrupt_input_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            writer = CaseRuntime(directory)
            dossier = writer.evaluate(fixture_manifest())
            run_record = writer.get_run(dossier.run_id)
            run_path = writer.store.runs / f"{dossier.run_id}.json"
            run_bytes = run_path.read_bytes()
            input_path = (
                writer.store.store.objects / f"{run_record['input_address'].split(':', 1)[1]}.json"
            )
            input_record = json.loads(input_path.read_text(encoding="utf-8"))
            input_record["case_id"] = "tampered-evaluate-input"
            input_path.write_text(json.dumps(input_record), encoding="utf-8")
            tampered_bytes = input_path.read_bytes()
            reader = CaseRuntime(directory)

            with (
                patch.object(
                    ObjectStore,
                    "put",
                    autospec=True,
                    wraps=ObjectStore.put,
                ) as put,
                patch.object(
                    RunStore,
                    "create_run",
                    autospec=True,
                    wraps=RunStore.create_run,
                ) as create_run,
            ):
                with self.assertRaisesRegex(ValidationError, "input"):
                    reader.evaluate(fixture_manifest())

            put.assert_not_called()
            create_run.assert_not_called()
            self.assertEqual(reader._logs, {})
            self.assertEqual(run_path.read_bytes(), run_bytes)
            self.assertEqual(input_path.read_bytes(), tampered_bytes)

    def test_repeated_offline_evaluate_rejects_a_missing_current_object(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            writer = CaseRuntime(directory)
            dossier = writer.evaluate(fixture_manifest())
            run_record = writer.get_run(dossier.run_id)
            run_path = writer.store.runs / f"{dossier.run_id}.json"
            run_bytes = run_path.read_bytes()
            dossier_path = (
                writer.store.store.objects
                / f"{run_record['dossier_address'].split(':', 1)[1]}.json"
            )
            dossier_path.unlink()
            remaining_objects = frozenset(writer.store.store.objects.glob("*.json"))
            reader = CaseRuntime(directory)

            with (
                patch.object(
                    ObjectStore,
                    "put",
                    autospec=True,
                    wraps=ObjectStore.put,
                ) as put,
                patch.object(
                    RunStore,
                    "create_run",
                    autospec=True,
                    wraps=RunStore.create_run,
                ) as create_run,
            ):
                with self.assertRaisesRegex(ValidationError, "invalid persisted artifacts"):
                    reader.evaluate(fixture_manifest())

            put.assert_not_called()
            create_run.assert_not_called()
            self.assertEqual(reader._logs, {})
            self.assertEqual(run_path.read_bytes(), run_bytes)
            self.assertEqual(
                frozenset(writer.store.store.objects.glob("*.json")),
                remaining_objects,
            )

    def test_repeated_rna_evaluate_rejects_a_missing_recorded_input_batch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            rna = _rna_consequence()
            writer = CaseRuntime(directory)
            dossier = writer.evaluate(fixture_manifest(), rna_consequences=(rna,))
            run_record = writer.get_run(dossier.run_id)
            run_path = writer.store.runs / f"{dossier.run_id}.json"
            run_bytes = run_path.read_bytes()
            event_record = writer.store.store.get(run_record["event_address"])
            rna_address = event_record["events"][0]["payload"]["rna_input_address"]
            rna_path = writer.store.store.objects / f"{rna_address.split(':', 1)[1]}.json"
            rna_path.unlink()
            remaining_objects = frozenset(writer.store.store.objects.glob("*.json"))
            reader = CaseRuntime(directory)

            with (
                patch.object(
                    ObjectStore,
                    "put",
                    autospec=True,
                    wraps=ObjectStore.put,
                ) as put,
                patch.object(
                    RunStore,
                    "create_run",
                    autospec=True,
                    wraps=RunStore.create_run,
                ) as create_run,
            ):
                with self.assertRaisesRegex(ValidationError, "RNA input object"):
                    reader.evaluate(fixture_manifest(), rna_consequences=(rna,))

            put.assert_not_called()
            create_run.assert_not_called()
            self.assertEqual(reader._logs, {})
            self.assertEqual(run_path.read_bytes(), run_bytes)
            self.assertEqual(
                frozenset(writer.store.store.objects.glob("*.json")),
                remaining_objects,
            )

    def test_review_rejects_rna_claim_absent_from_recorded_input_batch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest = fixture_manifest()
            recorded = _rna_consequence()
            runtime = CaseRuntime(directory)
            dossier = runtime.evaluate(manifest, rna_consequences=(recorded,))
            current_run = runtime.get_run(dossier.run_id)
            event_record = runtime.store.store.get(current_run["event_address"])
            rna_address = event_record["events"][0]["payload"]["rna_input_address"]

            rogue_prediction_id = "prediction:runtime:not-in-recorded-batch"
            rogue = replace(
                recorded,
                prediction_id=rogue_prediction_id,
                prediction_address=content_hash(
                    {"prediction_id": rogue_prediction_id},
                    prefix="regulatory-effect-prediction",
                ),
                expression_result_address=content_hash(
                    {"prediction_id": rogue_prediction_id, "component": "expression"},
                    prefix="expression-outlier",
                ),
                allelic_result_address=content_hash(
                    {"prediction_id": rogue_prediction_id, "component": "allelic"},
                    prefix="allelic-imbalance",
                ),
                reason_codes=("not_in_recorded_batch",),
            )
            self.assertNotEqual(rogue.content_address, recorded.content_address)
            forged_build = runtime.builder.build(
                manifest,
                dossier.run_id,
                rna_consequences=(rogue,),
                retained_owner_address=rna_address,
            )
            forged = runtime._make_dossier(
                manifest=manifest,
                run_id=dossier.run_id,
                input_address=dossier.input_address,
                hypotheses=forged_build.hypotheses,
                claims=forged_build.claims,
                experiments=runtime.planner.plan_many(forged_build.hypotheses),
                review=None,
                status=ResearchStatus.REVIEW_REQUIRED,
                event_head=dossier.event_head,
                warnings=forged_build.warnings,
                created_at=dossier.created_at,
                source_receipts=dossier.source_receipts,
                source_bundle_addresses=dossier.source_bundle_addresses,
            )
            runtime._validate_dossier_contract(forged, "forged persisted dossier")
            forged_address = runtime.store.store.put_at(
                forged.content_address,
                forged.to_dict(),
            )
            runtime.store.advance_run(
                dossier.run_id,
                expected_run=current_run,
                event_address=current_run["event_address"],
                dossier_address=forged_address,
            )
            before = runtime.get_run(dossier.run_id)
            object_names = frozenset(runtime.store.store.objects.glob("*.json"))

            with self.assertRaisesRegex(ValidationError, "not present in its recorded input"):
                runtime.review_run(dossier.run_id, _review(forged))

            self.assertEqual(runtime.get_run(dossier.run_id), before)
            self.assertEqual(
                frozenset(runtime.store.store.objects.glob("*.json")),
                object_names,
            )

    def test_rna_persistence_limits_fail_before_publication(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValidationError, "positive integer"):
                CaseRuntime(directory, rna_input_max_bytes=True)  # type: ignore[arg-type]

            runtime = CaseRuntime(directory, rna_input_max_bytes=1)
            with self.assertRaisesRegex(ValidationError, "persisted byte ceiling"):
                runtime.evaluate(
                    fixture_manifest(),
                    rna_consequences=(_rna_consequence(),),
                )
            self.assertEqual(runtime._logs, {})
            self.assertEqual(tuple(runtime.store.runs.glob("*.json")), ())
            self.assertEqual(tuple(runtime.store.store.objects.glob("*.json")), ())

        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            oversized_reasons = replace(
                _rna_consequence(),
                reason_codes=tuple(f"reason_{index}" for index in range(257)),
            )
            with self.assertRaisesRegex(ValidationError, "reason_codes"):
                runtime.evaluate(
                    fixture_manifest(),
                    rna_consequences=(oversized_reasons,),
                )
            self.assertEqual(tuple(runtime.store.runs.glob("*.json")), ())
            self.assertEqual(tuple(runtime.store.store.objects.glob("*.json")), ())

    def test_live_identity_is_resolved_before_collision_and_repeat_writes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest = fixture_manifest()

            class VersioningRetriever:
                def __init__(self) -> None:
                    self.calls = 0

                def enrich_manifest(self, value):
                    self.calls += 1
                    effective = replace(
                        value,
                        input_versions=dict(value.input_versions) | {"live_stub": "2026.09"},
                    )
                    bundle = ReferenceBundle.create(
                        variant_id=value.variants[0].variant_id,
                        context=value.context,
                        sequence=None,
                        elements=(),
                        raw_features=(),
                        receipts=(),
                        warnings=(),
                    )
                    return EnrichmentResult(effective, (bundle,), ())

            retriever = VersioningRetriever()
            runtime = CaseRuntime(directory, reference_retriever=retriever)
            offline = runtime.evaluate(manifest)
            live = runtime.evaluate(manifest, live_reference=True)
            self.assertNotEqual(live.run_id, offline.run_id)
            self.assertNotEqual(live.input_address, offline.input_address)
            self.assertEqual(
                runtime.load_run_snapshot(live.run_id).manifest.content_address,
                live.input_address,
            )
            before = _runtime_state(runtime, live)

            with (
                patch.object(
                    ObjectStore,
                    "put",
                    autospec=True,
                    wraps=ObjectStore.put,
                ) as put,
                patch.object(
                    RunStore,
                    "create_run",
                    autospec=True,
                    wraps=RunStore.create_run,
                ) as create_run,
            ):
                with self.assertRaisesRegex(ValidationError, "run already exists") as raised:
                    runtime.evaluate(manifest, live_reference=True)

            put.assert_not_called()
            create_run.assert_not_called()
            self.assertEqual(retriever.calls, 2)
            self.assertIsInstance(raised.exception.__cause__, StoreError)
            self.assertEqual(_runtime_state(runtime, live), before)

    def test_two_runtime_identical_evaluate_race_reuses_create_winner(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtimes = (CaseRuntime(directory), CaseRuntime(directory))
            barrier = threading.Barrier(2)
            results: Queue[object] = Queue()

            def run_evaluate(runtime: CaseRuntime) -> None:
                try:
                    barrier.wait(timeout=10)
                    results.put(runtime.evaluate(fixture_manifest()))
                except BaseException as exc:  # pragma: no cover - asserted below
                    results.put(exc)

            threads = tuple(
                threading.Thread(target=run_evaluate, args=(runtime,)) for runtime in runtimes
            )
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=15)

            self.assertFalse(any(thread.is_alive() for thread in threads))
            outcomes = [results.get(timeout=2) for _ in runtimes]
            self.assertTrue(all(isinstance(item, Dossier) for item in outcomes), outcomes)
            dossiers = tuple(cast(Dossier, item) for item in outcomes)
            self.assertEqual(dossiers[0].to_dict(), dossiers[1].to_dict())
            run_record = runtimes[0].get_run(dossiers[0].run_id)
            self.assertEqual(run_record["event_history"], [run_record["event_address"]])
            self.assertEqual(run_record["dossier_history"], [run_record["dossier_address"]])
            self.assertEqual(run_record["dossier_address"], dossiers[0].content_address)
            persisted_events = runtimes[0].store.store.get(run_record["event_address"])
            for runtime in runtimes:
                self.assertEqual(
                    runtime._logs[dossiers[0].run_id].to_record(),
                    persisted_events,
                )

    def test_two_runtime_evaluations_share_callback_isolation(self) -> None:
        manifest = fixture_manifest()
        reference_bundle = ReferenceBundle.create(
            variant_id=manifest.variants[0].variant_id,
            context=manifest.context,
            sequence=None,
            elements=(),
            raw_features=(),
            receipts=(),
            warnings=(),
        )
        original_plan_many = vars(ExperimentPlanner)["plan_many"]
        mutation_active = threading.Event()
        second_attempted = threading.Event()
        second_completed = threading.Event()
        overlap_observed: list[bool] = []
        results: Queue[tuple[str, object]] = Queue()

        class TemporarilyConfiguredRetriever:
            @staticmethod
            def enrich_manifest(value):
                ExperimentPlanner.plan_many = lambda _planner, _hypotheses: ()
                mutation_active.set()
                try:
                    if not second_attempted.wait(timeout=10):
                        raise AssertionError("second runtime did not attempt evaluation")
                    overlap_observed.append(second_completed.wait(timeout=0.5))
                finally:
                    ExperimentPlanner.plan_many = original_plan_many
                return EnrichmentResult(value, (reference_bundle,), ())

        def run_first(runtime: CaseRuntime) -> None:
            try:
                results.put(("first", runtime.evaluate(manifest, live_reference=True)))
            except BaseException as exc:  # pragma: no cover - asserted below
                results.put(("first_error", exc))

        def run_second(runtime: CaseRuntime) -> None:
            second_attempted.set()
            try:
                results.put(("second", runtime.evaluate(manifest)))
            except BaseException as exc:  # pragma: no cover - asserted below
                results.put(("second_error", exc))
            finally:
                second_completed.set()

        try:
            with (
                tempfile.TemporaryDirectory() as first_directory,
                tempfile.TemporaryDirectory() as second_directory,
            ):
                first_runtime = CaseRuntime(
                    first_directory,
                    reference_retriever=TemporarilyConfiguredRetriever(),
                )
                second_runtime = CaseRuntime(second_directory)
                first_thread = threading.Thread(target=run_first, args=(first_runtime,))
                second_thread = threading.Thread(target=run_second, args=(second_runtime,))
                first_thread.start()
                self.assertTrue(mutation_active.wait(timeout=10))
                second_thread.start()
                first_thread.join(timeout=15)
                second_thread.join(timeout=15)

                self.assertFalse(first_thread.is_alive())
                self.assertFalse(second_thread.is_alive())
                outcomes = dict(results.get(timeout=2) for _ in range(2))
                self.assertEqual(set(outcomes), {"first", "second"}, outcomes)
                self.assertEqual(overlap_observed, [False])
                self.assertGreater(len(cast(Dossier, outcomes["second"]).experiments), 0)
                self.assertIs(vars(ExperimentPlanner)["plan_many"], original_plan_many)
        finally:
            ExperimentPlanner.plan_many = original_plan_many
            second_attempted.set()

    def test_callback_cannot_nest_a_second_runtime_with_substituted_configuration(
        self,
    ) -> None:
        manifest = fixture_manifest()
        variant = manifest.variants[0]
        nested_manifest = replace(
            manifest,
            case_id="case-nested-runtime",
            variants=(
                variant,
                replace(
                    variant,
                    variant_id="var-nested-runtime",
                    start=variant.start + 1,
                    end=variant.end + 1,
                ),
            ),
        )
        reference_bundle = ReferenceBundle.create(
            variant_id=variant.variant_id,
            context=manifest.context,
            sequence=None,
            elements=(),
            raw_features=(),
            receipts=(),
            warnings=(),
        )
        nested_error: list[BaseException] = []

        with (
            tempfile.TemporaryDirectory() as outer_directory,
            tempfile.TemporaryDirectory() as nested_directory,
        ):
            nested_runtime = CaseRuntime(
                nested_directory,
                experiment_limits=ExperimentPlanningLimits(max_hypotheses=1),
            )
            original_planner = nested_runtime.planner

            class NestedRetriever:
                @staticmethod
                def enrich_manifest(value):
                    nested_runtime.planner = ExperimentPlanner()
                    vars(nested_runtime)["_validate_event_payload_size"] = (
                        lambda *_args, **_kwargs: None
                    )
                    context_token = runtime_module._ACTIVE_EVALUATION_RUNTIME_IDS.set(  # noqa: SLF001
                        frozenset()
                    )
                    try:
                        nested_runtime.evaluate(nested_manifest)
                    except BaseException as exc:
                        nested_error.append(exc)
                    finally:
                        runtime_module._ACTIVE_EVALUATION_RUNTIME_IDS.reset(  # noqa: SLF001
                            context_token
                        )
                        nested_runtime.planner = original_planner
                        vars(nested_runtime).pop("_validate_event_payload_size", None)
                    return EnrichmentResult(value, (reference_bundle,), ())

            outer_runtime = CaseRuntime(
                outer_directory,
                reference_retriever=NestedRetriever(),
            )
            outer_dossier = outer_runtime.evaluate(manifest, live_reference=True)

            self.assertEqual(outer_dossier.case_id, manifest.case_id)
            self.assertEqual(len(nested_error), 1)
            self.assertIsInstance(nested_error[0], ValidationError)
            self.assertRegex(str(nested_error[0]), "recursive runtime evaluation")
            self.assertIs(nested_runtime.planner, original_planner)
            self.assertNotIn("_validate_event_payload_size", vars(nested_runtime))
            self.assertEqual(tuple(nested_runtime.store.runs.glob("*.json")), ())
            self.assertEqual(tuple(nested_runtime.store.store.objects.glob("*.json")), ())
            with self.assertRaisesRegex(ValidationError, "hypotheses exceeds"):
                nested_runtime.evaluate(nested_manifest)
            self.assertEqual(nested_runtime.evaluate(manifest).case_id, manifest.case_id)
            outer_retry_manifest = replace(
                manifest,
                case_id="case-outer-runtime-retry",
            )
            self.assertEqual(
                outer_runtime.evaluate(
                    outer_retry_manifest,
                    live_reference=True,
                ).case_id,
                outer_retry_manifest.case_id,
            )
            self.assertEqual(len(nested_error), 2)
            self.assertRegex(str(nested_error[1]), "recursive runtime evaluation")

    def test_runtime_rejects_a_preexisting_instance_method_shadow(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            shadow_called = False

            def shadow_capture():
                nonlocal shadow_called
                shadow_called = True
                raise AssertionError("instance shadow must not execute")

            vars(runtime)["_capture_evaluation_configuration"] = shadow_capture

            with self.assertRaisesRegex(ValidationError, "non-canonical instance state"):
                runtime.evaluate(fixture_manifest())

            self.assertFalse(shadow_called)
            self.assertEqual(tuple(runtime.store.runs.glob("*.json")), ())
            self.assertEqual(tuple(runtime.store.store.objects.glob("*.json")), ())
            vars(runtime).pop("_capture_evaluation_configuration")
            self.assertEqual(runtime.evaluate(fixture_manifest()).case_id, "case-demo-001")

    def test_callback_class_and_namespace_swaps_restore_before_instance_setters(self) -> None:
        manifest = fixture_manifest()
        reference_bundle = ReferenceBundle.create(
            variant_id=manifest.variants[0].variant_id,
            context=manifest.context,
            sequence=None,
            elements=(),
            raw_features=(),
            receipts=(),
            warnings=(),
        )

        class ReconfiguredRuntime(CaseRuntime):
            def __setattr__(self, _name, _value) -> None:
                raise RuntimeError("runtime setter is unavailable")

            def __getattribute__(self, name):
                if name == "__dict__":
                    raise RuntimeError("runtime namespace lookup is unavailable")
                return object.__getattribute__(self, name)

        class ReconfiguredBuilder(HypothesisBuilder):
            def __setattr__(self, _name, _value) -> None:
                raise RuntimeError("builder setter is unavailable")

        for selected_target in ("runtime", "builder"):
            with self.subTest(target=selected_target), tempfile.TemporaryDirectory() as directory:
                calls = 0

                class ReconfiguringRetriever:
                    def __init__(self, target_name: str) -> None:
                        self.target_name = target_name
                        self.runtime: CaseRuntime | None = None

                    def enrich_manifest(self, value):
                        nonlocal calls
                        calls += 1
                        if calls == 1:
                            if self.runtime is None:  # pragma: no cover - fixture invariant
                                raise AssertionError("runtime fixture is not attached")
                            target = (
                                self.runtime
                                if self.target_name == "runtime"
                                else self.runtime.builder
                            )
                            replacement_namespace = dict(vars(target))
                            replacement_namespace["temporary_marker"] = self.target_name
                            object.__setattr__(target, "__dict__", replacement_namespace)
                            object.__setattr__(
                                target,
                                "__class__",
                                (
                                    ReconfiguredRuntime
                                    if self.target_name == "runtime"
                                    else ReconfiguredBuilder
                                ),
                            )
                        return EnrichmentResult(value, (reference_bundle,), ())

                retriever = ReconfiguringRetriever(selected_target)
                runtime = CaseRuntime(
                    directory,
                    reference_retriever=retriever,
                )
                retriever.runtime = runtime
                original_runtime_namespace = vars(runtime)
                original_builder = runtime.builder
                original_builder_namespace = vars(original_builder)

                with self.assertRaises(ValidationError):
                    runtime.evaluate(manifest, live_reference=True)

                self.assertIs(type(runtime), CaseRuntime)
                self.assertIs(vars(runtime), original_runtime_namespace)
                self.assertIs(runtime.builder, original_builder)
                self.assertIs(type(runtime.builder), HypothesisBuilder)
                self.assertIs(vars(runtime.builder), original_builder_namespace)
                self.assertNotIn("temporary_marker", vars(runtime))
                self.assertNotIn("temporary_marker", vars(runtime.builder))
                self.assertEqual(tuple(runtime.store.runs.glob("*.json")), ())
                self.assertEqual(tuple(runtime.store.store.objects.glob("*.json")), ())
                retry = runtime.evaluate(manifest, live_reference=True)
                self.assertEqual(retry.case_id, manifest.case_id)

    def test_repeated_evaluate_cannot_reuse_an_assigned_draft(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            dossier = runtime.evaluate(fixture_manifest())
            runtime.assign_review(
                dossier.run_id,
                assignment_id="assignment-before-repeat",
                reviewer="assigned-reviewer",
            )
            before = _runtime_state(runtime, dossier)

            with (
                patch.object(
                    ObjectStore,
                    "put",
                    autospec=True,
                    wraps=ObjectStore.put,
                ) as put,
                patch.object(
                    RunStore,
                    "create_run",
                    autospec=True,
                    wraps=RunStore.create_run,
                ) as create_run,
            ):
                with self.assertRaisesRegex(ValidationError, "run already exists") as raised:
                    runtime.evaluate(fixture_manifest())

            put.assert_not_called()
            create_run.assert_not_called()
            self.assertIsInstance(raised.exception.__cause__, StoreError)
            self.assertEqual(_runtime_state(runtime, dossier), before)

    def test_repeated_deterministic_evaluate_cannot_rewind_reviewed_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            dossier = runtime.evaluate(fixture_manifest())
            released = runtime.review(dossier, _review(dossier))
            before_run = runtime.get_run(dossier.run_id)
            before_cached = runtime._logs[dossier.run_id].to_record()
            run_path = runtime.store.runs / f"{dossier.run_id}.json"
            before_run_bytes = run_path.read_bytes()

            with self.assertRaisesRegex(ValidationError, "run already exists") as raised:
                runtime.evaluate(fixture_manifest())

            self.assertIsInstance(raised.exception.__cause__, StoreError)
            self.assertEqual(run_path.read_bytes(), before_run_bytes)
            self.assertEqual(runtime.get_run(dossier.run_id), before_run)
            self.assertEqual(
                runtime._logs[dossier.run_id].to_record(),
                before_cached,
            )
            self.assertEqual(before_run["dossier_address"], released.content_address)


if __name__ == "__main__":
    unittest.main()
