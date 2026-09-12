from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch

import glio_noncode.runtime as runtime_module
from glio_noncode.atlas import AtlasBundle, AtlasObservation, AtlasQuery, PublicAtlasRetriever
from glio_noncode.data_sources import (
    EnrichmentResult,
    FetchReceipt,
    FetchStatus,
    ReferenceBundle,
    SequenceSlice,
    SourcePayload,
)
from glio_noncode.errors import SourceError, ValidationError
from glio_noncode.events import EventLog
from glio_noncode.experiments import ExperimentPlanningLimits
from glio_noncode.hypotheses import HypothesisWorkLimits
from glio_noncode.models import (
    EvidenceState,
    EvidenceTier,
    ReferenceContext,
    ReviewDecision,
    ReviewState,
    VariantIdentity,
)
from glio_noncode.policy import PolicyLimits
from glio_noncode.replay import ReplayVerifier
from glio_noncode.reports import render_markdown, summarize
from glio_noncode.runtime import CaseRuntime
from glio_noncode.sequence_inference import SequenceInference
from glio_noncode.serialization import canonical_bytes, content_hash
from glio_noncode.validation import ContractValidator, ReleaseGate

from .helpers import fixture_manifest


def _receipt(label: str) -> FetchReceipt:
    return FetchReceipt(
        source_id="SRC-RUNTIME-TEST",
        source_version="fixture-1",
        url=f"https://runtime.example/{label}",
        request_hash=content_hash({"request": label}),
        response_hash=content_hash({"response": label}),
        status=FetchStatus.FETCHED,
        http_status=200,
        attempts=1,
        retrieved_at="2026-09-07T12:00:00+00:00",
        elapsed_seconds=0.01,
        cache_expires_at=None,
    )


class _FailingEncodeClient:
    def __init__(self, message: str) -> None:
        self.message = message

    def search_experiments(
        self,
        *,
        assay_title: str | None = None,
        biosample_ontology_term_name: str | None = None,
        organism: str = "Homo sapiens",
        limit: int = 25,
    ) -> SourcePayload:
        raise SourceError(self.message)


def _replayable_atlas_bundle(
    variant: VariantIdentity,
    context: ReferenceContext,
    reference_bundle: ReferenceBundle,
    *,
    atlas_warning: str | None = None,
) -> AtlasBundle:
    query = AtlasQuery(
        variant_id=variant.variant_id,
        include_encode_catalog=atlas_warning is not None,
    )
    retriever = PublicAtlasRetriever(
        encode_client=(
            None if atlas_warning is None else _FailingEncodeClient(atlas_warning)
        )
    )
    return retriever.retrieve(
        variant,
        context,
        query=query,
        reference_bundle=reference_bundle,
    )


class RuntimeTests(unittest.TestCase):
    def test_persisted_source_closure_rejects_unknown_lifecycle_suffix_events(self) -> None:
        manifest = fixture_manifest()
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            dossier = runtime.evaluate(manifest)
            snapshot = runtime.load_run_snapshot(dossier.run_id)
            extended = EventLog(dossier.run_id)
            for event in snapshot.event_log.all():
                extended.append(
                    event.event_type,
                    event.payload,
                    event_id=event.event_id,
                )
            extended.append(
                "unrecognized_runtime_extension",
                {},
                event_id=f"evt-{dossier.run_id}-unknown",
            )

            with self.assertRaisesRegex(ValidationError, "unknown event type"):
                runtime._validate_persisted_source_closure(  # noqa: SLF001
                    manifest=snapshot.manifest,
                    dossier=snapshot.dossier,
                    events=extended.all(),
                    rna_address=None,
                )

    def test_source_event_warnings_must_remain_in_the_dossier_ledger(self) -> None:
        manifest = fixture_manifest()

        for include_atlas, expected_message in (
            (False, "persisted reference warnings"),
            (True, "persisted atlas warnings"),
        ):
            with (
                self.subTest(include_atlas=include_atlas),
                tempfile.TemporaryDirectory() as directory,
            ):
                reference_warnings = () if include_atlas else ("reference warning",)
                reference_bundle = ReferenceBundle.create(
                    variant_id=manifest.variants[0].variant_id,
                    context=manifest.context,
                    sequence=None,
                    elements=(),
                    raw_features=(),
                    receipts=(),
                    warnings=reference_warnings,
                )

                class StubRetriever:
                    def __init__(self, bundle, warnings):
                        self.bundle = bundle
                        self.warnings = warnings

                    def enrich_manifest(self, value):
                        return EnrichmentResult(
                            value,
                            (self.bundle,),
                            self.warnings,
                        )

                class StubAtlas:
                    def __init__(self, bundle):
                        self.bundle = bundle

                    def retrieve(self, variant, context):
                        return _replayable_atlas_bundle(
                            variant,
                            context,
                            self.bundle,
                            atlas_warning="atlas warning",
                        )

                runtime = CaseRuntime(
                    directory,
                    reference_retriever=StubRetriever(
                        reference_bundle,
                        reference_warnings,
                    ),
                    atlas_retriever=(
                        StubAtlas(reference_bundle)
                        if include_atlas
                        else None
                    ),
                )
                dossier = runtime.evaluate(manifest, live_reference=True)
                snapshot = runtime.load_run_snapshot(dossier.run_id)
                forged_dossier = runtime._readdress(  # noqa: SLF001
                    replace(dossier, warnings=())
                )
                rewritten = EventLog(dossier.run_id)
                for event in snapshot.event_log.all():
                    payload = dict(event.payload)
                    if event.event_type == "hypotheses_built":
                        payload["warnings"] = []
                    rewritten.append(
                        event.event_type,
                        payload,
                        event_id=event.event_id,
                    )

                with self.assertRaisesRegex(ValidationError, expected_message):
                    runtime._validate_persisted_source_closure(  # noqa: SLF001
                        manifest=snapshot.manifest,
                        dossier=forged_dossier,
                        events=rewritten.all(),
                        rna_address=None,
                    )

    def test_runtime_never_retains_a_source_object_its_loader_cannot_reopen(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            runtime.validator = ContractValidator(
                limits=replace(runtime.validator.limits, max_canonical_bytes=16)
            )
            with self.assertRaisesRegex(ValidationError, "persisted object byte ceiling"):
                runtime._retain_source_record(  # noqa: SLF001 - focused runtime boundary
                    {},
                    {"payload": "larger-than-sixteen-bytes"},
                    0,
                    label="fixture",
                )

    def test_source_closure_uses_one_aggregate_publication_and_replay_budget(self) -> None:
        manifest = fixture_manifest()

        class StubRetriever:
            def enrich_manifest(self, value):
                bundle = ReferenceBundle.create(
                    variant_id=value.variants[0].variant_id,
                    context=value.context,
                    sequence=None,
                    elements=(),
                    raw_features=(),
                    receipts=(),
                    warnings=(),
                )
                return EnrichmentResult(value, (bundle,), ())

        class TrackingRetriever(StubRetriever):
            def __init__(self) -> None:
                self.calls = 0

            def enrich_manifest(self, value):
                self.calls += 1
                return super().enrich_manifest(value)

        tracker = TrackingRetriever()
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(
                directory,
                reference_retriever=tracker,
                source_closure_max_bytes=len(canonical_bytes(manifest.to_dict())),
            )
            with self.assertRaisesRegex(ValidationError, "aggregate canonical byte ceiling"):
                runtime.evaluate(manifest, live_reference=True)
            self.assertEqual(tracker.calls, 0)
            self.assertEqual(tuple(runtime.store.store.objects.glob("*.json")), ())

        with tempfile.TemporaryDirectory() as directory:
            writer = CaseRuntime(directory, reference_retriever=StubRetriever())
            dossier = writer.evaluate(manifest, live_reference=True)
            reader = CaseRuntime(directory, source_closure_max_bytes=1)
            with self.assertRaisesRegex(ValidationError, "aggregate canonical byte ceiling"):
                reader.load_run_snapshot(dossier.run_id)

        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(
                directory,
                reference_retriever=StubRetriever(),
                source_closure_max_bytes=1,
            )
            with self.assertRaisesRegex(ValidationError, "aggregate canonical byte ceiling"):
                runtime.evaluate(manifest, live_reference=True)
            self.assertEqual(tuple(runtime.store.store.objects.glob("*.json")), ())
            self.assertEqual(tuple(runtime.store.runs.glob("*.json")), ())

    def test_live_reference_callback_inputs_and_nested_results_are_detached(self) -> None:
        manifest = fixture_manifest()
        original = manifest.to_dict()

        class MutatingInputRetriever:
            def enrich_manifest(self, value):
                object.__setattr__(value, "requested_by", "mutated-by-retriever")
                bundle = ReferenceBundle.create(
                    variant_id=value.variants[0].variant_id,
                    context=value.context,
                    sequence=None,
                    elements=(),
                    raw_features=(),
                    receipts=(),
                    warnings=(),
                )
                return EnrichmentResult(value, (bundle,), ())

        class MutatingBundleRetriever:
            def enrich_manifest(self, value):
                bundle = ReferenceBundle.create(
                    variant_id=value.variants[0].variant_id,
                    context=value.context,
                    sequence=None,
                    elements=(),
                    raw_features=(),
                    receipts=(),
                    warnings=(),
                )
                result = EnrichmentResult(value, (bundle,), ())
                object.__setattr__(bundle, "raw_features", ({"forged": True},))
                return result

        scenarios = (
            (MutatingInputRetriever(), "mutated its manifest input"),
            (MutatingBundleRetriever(), "content_address does not match"),
        )
        for retriever, message in scenarios:
            with self.subTest(message=message), tempfile.TemporaryDirectory() as directory:
                runtime = CaseRuntime(directory, reference_retriever=retriever)
                with self.assertRaisesRegex(ValidationError, message):
                    runtime.evaluate(manifest, live_reference=True)
                self.assertEqual(manifest.to_dict(), original)
                self.assertEqual(tuple(runtime.store.store.objects.glob("*.json")), ())
                self.assertEqual(tuple(runtime.store.runs.glob("*.json")), ())

    def test_atlas_callback_sequence_analysis_must_match_retained_reference(self) -> None:
        manifest = fixture_manifest()
        variant = manifest.variants[0]
        retained_receipt = _receipt("retained-sequence")
        retained_sequence = SequenceSlice(
            assembly=manifest.context.genome_build,
            chromosome=variant.chromosome,
            start=variant.start,
            end=variant.start + 3,
            sequence="ACGT",
            source_id=retained_receipt.source_id,
            receipt=retained_receipt,
        )
        retained_bundle = ReferenceBundle.create(
            variant_id=variant.variant_id,
            context=manifest.context,
            sequence=retained_sequence,
            elements=(),
            raw_features=(),
            receipts=(retained_receipt,),
            warnings=(),
        )
        foreign_receipt = _receipt("foreign-sequence")
        foreign_sequence = SequenceSlice(
            assembly=manifest.context.genome_build,
            chromosome=variant.chromosome,
            start=variant.start,
            end=variant.start + 3,
            sequence="ATGT",
            source_id=foreign_receipt.source_id,
            receipt=foreign_receipt,
        )
        foreign_analysis = SequenceInference().analyze(variant, foreign_sequence)

        class StubRetriever:
            def enrich_manifest(self, value):
                return EnrichmentResult(value, (retained_bundle,), ())

        class ForgedAtlas:
            def retrieve(self, callback_variant, context):
                valid = _replayable_atlas_bundle(
                    callback_variant,
                    context,
                    retained_bundle,
                )
                return AtlasBundle.create(
                    variant=callback_variant,
                    context=context,
                    query=valid.query,
                    source_bundle_address=retained_bundle.content_address,
                    replay_inputs=valid.replay_inputs,
                    observations=valid.observations,
                    receipts=valid.receipts,
                    warnings=valid.warnings,
                    created_at=valid.created_at,
                    sequence_analysis=foreign_analysis,
                    uncertainty=valid.uncertainty,
                    track_reports=valid.track_reports,
                )

        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(
                directory,
                reference_retriever=StubRetriever(),
                atlas_retriever=ForgedAtlas(),
            )
            with self.assertRaisesRegex(ValidationError, "reference hash"):
                runtime.evaluate(manifest, live_reference=True)
            self.assertEqual(tuple(runtime.store.store.objects.glob("*.json")), ())
            self.assertEqual(tuple(runtime.store.runs.glob("*.json")), ())

    def test_live_reference_cannot_rewrite_or_inject_base_manifest_state(self) -> None:
        manifest = fixture_manifest()
        unbundled = replace(
            manifest.candidate_elements[0],
            element_id="unbundled-live-element",
            start=manifest.candidate_elements[0].start + 3,
            end=manifest.candidate_elements[0].end + 3,
        )
        changed_versions = dict(manifest.input_versions)
        first_version_key = next(iter(changed_versions))
        changed_versions[first_version_key] = "rewritten-version"
        scenarios = (
            replace(manifest, case_id=manifest.case_id + "-rewritten"),
            replace(manifest, subject_id=manifest.subject_id + "-rewritten"),
            replace(manifest, requested_by=manifest.requested_by + "-rewritten"),
            replace(manifest, metadata={"injected": True}),
            replace(
                manifest,
                variants=(replace(manifest.variants[0], chromosome="chr8"),),
            ),
            replace(manifest, candidate_elements=()),
            replace(
                manifest,
                candidate_elements=manifest.candidate_elements + (unbundled,),
            ),
            replace(manifest, input_versions=changed_versions),
        )

        for changed in scenarios:
            with self.subTest(changed=changed.content_address):
                class StubRetriever:
                    def __init__(self, result):
                        self.result = result

                    def enrich_manifest(self, _value):
                        bundles = tuple(
                            ReferenceBundle.create(
                                variant_id=variant.variant_id,
                                context=self.result.context,
                                sequence=None,
                                elements=(),
                                raw_features=(),
                                receipts=(),
                                warnings=(),
                            )
                            for variant in self.result.variants
                        )
                        return EnrichmentResult(self.result, bundles, ())

                with tempfile.TemporaryDirectory() as directory:
                    runtime = CaseRuntime(
                        directory,
                        reference_retriever=StubRetriever(changed),
                    )
                    with self.assertRaisesRegex(ValidationError, "reference enrichment"):
                        runtime.evaluate(manifest, live_reference=True)
                    self.assertEqual(tuple(runtime.store.store.objects.glob("*.json")), ())
                    self.assertEqual(tuple(runtime.store.runs.glob("*.json")), ())

    def test_evaluate_persists_replayable_dossier(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            dossier = runtime.evaluate(fixture_manifest())
            self.assertTrue(dossier.research_use_only)
            self.assertGreater(len(dossier.hypotheses), 0)
            self.assertGreater(len(dossier.evidence), 0)
            self.assertTrue(runtime.store.store.exists(dossier.content_address))
            run = runtime.get_run(dossier.run_id)
            stored = runtime.get_dossier(dossier.content_address)
            self.assertEqual(stored["content_address"], dossier.content_address)
            self.assertEqual(run["dossier_address"], dossier.content_address)

    def test_review_changes_status_and_creates_new_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            dossier = runtime.evaluate(fixture_manifest())
            review = ReviewDecision(
                review_id="review-1",
                case_id=dossier.case_id,
                reviewer="scientific-reviewer",
                state=ReviewState.ACCEPTED,
                reviewed_hypothesis_ids=(dossier.hypotheses[0].hypothesis_id,),
                rationale="Checked the displayed edge claims and retained alternatives.",
                checked_claim_ids=tuple(claim.evidence_id for claim in dossier.evidence),
            )
            released = runtime.review(dossier, review)
            self.assertEqual(released.status.value, "released_research")
            self.assertNotEqual(released.content_address, dossier.content_address)
            self.assertTrue(released.is_releasable)
            self.assertTrue(ReleaseGate().check(released).valid)

    def test_replay_verifier_detects_valid_chain(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            dossier = runtime.evaluate(fixture_manifest())
            run = runtime.get_run(dossier.run_id)
            events = runtime.store.store.get(run["event_address"])
            stored_dossier = runtime.get_dossier(run["dossier_address"])
            report = ReplayVerifier().verify(run, events, stored_dossier)
            self.assertTrue(report.event_chain_valid)
            self.assertTrue(report.stored_dossier_matches_address)
            self.assertFalse(report.warnings)

    def test_summary_and_markdown_preserve_edge_details(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            dossier = CaseRuntime(directory).evaluate(fixture_manifest())
            summary = summarize(dossier)
            markdown = render_markdown(dossier)
            self.assertEqual(summary.case_id, dossier.case_id)
            self.assertIn("Evidence ledger", markdown)
            self.assertIn(dossier.hypotheses[0].element_id, markdown)

    def test_manifest_contract_reports_missing_versions_as_warning(self) -> None:
        report = ContractValidator().validate_manifest(fixture_manifest())
        self.assertTrue(report.valid)
        self.assertFalse(any(issue.code == "missing_input_versions" for issue in report.issues))

    def test_live_reference_enrichment_is_persisted_with_dossier_provenance(self) -> None:
        manifest = fixture_manifest()
        live_element = replace(
            manifest.candidate_elements[0],
            element_id="element-live-added",
            start=manifest.candidate_elements[0].start + 100,
            end=manifest.candidate_elements[0].end + 100,
        )
        effective = replace(
            manifest,
            candidate_elements=manifest.candidate_elements + (live_element,),
            input_versions=dict(manifest.input_versions) | {"live_stub": "2026.09"},
        )

        class StubRetriever:
            def enrich_manifest(self, value):
                bundle = ReferenceBundle.create(
                    variant_id=value.variants[0].variant_id,
                    context=value.context,
                    sequence=None,
                    elements=(live_element,),
                    raw_features=(),
                    receipts=(),
                    warnings=(),
                )
                return EnrichmentResult(effective, (bundle,), ())

        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory, reference_retriever=StubRetriever())
            dossier = runtime.evaluate(
                manifest,
                live_reference=True,
            )
            snapshot = runtime.load_run_snapshot(dossier.run_id)
            run = runtime.get_run(dossier.run_id)
            self.assertEqual(snapshot.manifest, effective)
            self.assertEqual(run["input_address"], effective.content_address)
            self.assertEqual(dossier.input_address, effective.content_address)
            self.assertNotEqual(dossier.input_address, manifest.content_address)
            self.assertTrue(
                all(
                    dossier.input_address in hypothesis.provenance
                    for hypothesis in dossier.hypotheses
                )
            )
            self.assertEqual(len(dossier.source_bundle_addresses), 2)
            self.assertEqual(dossier.source_bundle_addresses[0], manifest.content_address)
            self.assertEqual(
                runtime.store.store.get(dossier.source_bundle_addresses[0]),
                manifest.to_dict(),
            )
            self.assertTrue(dossier.source_bundle_addresses[1].startswith("sha256:"))
            self.assertEqual(len(dossier.source_receipts), 0)
            self.assertTrue(
                CaseRuntime(directory).store.store.exists(dossier.source_bundle_addresses[0])
            )

    def test_optional_atlas_retriever_adds_reference_claims_and_bundle(self) -> None:
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

        class StubRetriever:
            def enrich_manifest(self, value):
                return EnrichmentResult(value, (reference_bundle,), ())

        class StubAtlas:
            def retrieve(self, variant, context):
                return _replayable_atlas_bundle(
                    variant,
                    context,
                    reference_bundle,
                )

        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(
                directory,
                reference_retriever=StubRetriever(),
                atlas_retriever=StubAtlas(),
            )
            dossier = runtime.evaluate(manifest, live_reference=True)
            snapshot = runtime.load_run_snapshot(dossier.run_id)
            self.assertEqual(snapshot.dossier, dossier)
            self.assertEqual(len(dossier.source_bundle_addresses), 4)
            atlas_event = next(
                event
                for event in snapshot.event_log.all()
                if event.event_type == "public_atlas_collected"
            )
            replay_addresses = tuple(atlas_event.payload["replay_input_addresses"])
            bundle_addresses = tuple(atlas_event.payload["bundle_addresses"])
            self.assertEqual(len(replay_addresses), 1)
            self.assertEqual(len(bundle_addresses), 1)
            self.assertEqual(
                dossier.source_bundle_addresses[-2:],
                (replay_addresses[0], bundle_addresses[0]),
            )
            self.assertTrue(
                any(claim.channel == "reference_annotation" for claim in dossier.evidence)
            )
            atlas_claim = next(
                claim for claim in dossier.evidence if claim.channel == "reference_annotation"
            )
            matching_edges = tuple(
                edge
                for hypothesis in dossier.hypotheses
                for edge in hypothesis.edges
                if atlas_claim.evidence_id in edge.claim_ids
            )
            self.assertEqual(len(matching_edges), 1)
            self.assertEqual(matching_edges[0].edge_id, atlas_claim.edge_id)
            self.assertEqual(summarize(dossier).orphan_claim_count, 0)

    def test_atlas_event_pair_arrays_are_complete_disjoint_and_variant_ordered(self) -> None:
        base = fixture_manifest()
        second_variant = replace(
            base.variants[0],
            variant_id="variant-atlas-pair-002",
            start=base.variants[0].start + 50,
            end=base.variants[0].end + 50,
        )
        manifest = replace(base, variants=(base.variants[0], second_variant))
        reference_bundles = tuple(
            ReferenceBundle.create(
                variant_id=variant.variant_id,
                context=manifest.context,
                sequence=None,
                elements=(),
                raw_features=(),
                receipts=(),
                warnings=(),
            )
            for variant in manifest.variants
        )
        reference_by_variant = {bundle.variant_id: bundle for bundle in reference_bundles}

        class StubRetriever:
            def enrich_manifest(self, value):
                return EnrichmentResult(value, reference_bundles, ())

        class StubAtlas:
            def retrieve(self, variant, context):
                return _replayable_atlas_bundle(
                    variant,
                    context,
                    reference_by_variant[variant.variant_id],
                )

        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(
                directory,
                reference_retriever=StubRetriever(),
                atlas_retriever=StubAtlas(),
            )
            dossier = runtime.evaluate(manifest, live_reference=True)
            snapshot = runtime.load_run_snapshot(dossier.run_id)
            events = snapshot.event_log.all()
            atlas_event = next(
                event for event in events if event.event_type == "public_atlas_collected"
            )
            original_payload = dict(atlas_event.payload)
            replay_addresses = list(original_payload["replay_input_addresses"])
            bundle_addresses = list(original_payload["bundle_addresses"])
            self.assertEqual(len(replay_addresses), len(manifest.variants))
            self.assertEqual(len(bundle_addresses), len(manifest.variants))
            self.assertFalse(set(replay_addresses) & set(bundle_addresses))
            self.assertEqual(
                dossier.source_bundle_addresses[-4:],
                tuple(
                    address
                    for pair in zip(replay_addresses, bundle_addresses, strict=True)
                    for address in pair
                ),
            )

            malformed_payloads = (
                (
                    {
                        key: value
                        for key, value in original_payload.items()
                        if key != "replay_input_addresses"
                    },
                    "exact array",
                ),
                (
                    original_payload | {"replay_input_addresses": replay_addresses[:-1]},
                    "equal length",
                ),
                (
                    original_payload
                    | {"replay_input_addresses": [replay_addresses[0], replay_addresses[0]]},
                    "must be unique",
                ),
                (
                    original_payload
                    | {
                        "replay_input_addresses": [
                            bundle_addresses[0],
                            replay_addresses[1],
                        ]
                    },
                    "must be disjoint",
                ),
                (
                    original_payload | {"bundle_addresses": list(reversed(bundle_addresses))},
                    "event lineage",
                ),
            )
            for payload, expected_error in malformed_payloads:
                with self.subTest(expected_error=expected_error):
                    altered_log = EventLog(dossier.run_id)
                    for event in events:
                        altered_log.append(
                            event.event_type,
                            (
                                payload
                                if event.event_type == "public_atlas_collected"
                                else event.payload
                            ),
                            event_id=event.event_id,
                        )
                    with self.assertRaisesRegex(ValidationError, expected_error):
                        runtime._validate_persisted_source_closure(  # noqa: SLF001
                            manifest=snapshot.manifest,
                            dossier=snapshot.dossier,
                            events=altered_log.all(),
                            rna_address=None,
                        )

    def test_atlas_loader_rejects_missing_or_substituted_pair_members(self) -> None:
        manifest = fixture_manifest()
        variant = manifest.variants[0]
        reference_bundle = ReferenceBundle.create(
            variant_id=variant.variant_id,
            context=manifest.context,
            sequence=None,
            elements=(),
            raw_features=(),
            receipts=(),
            warnings=(),
        )

        class StubRetriever:
            def enrich_manifest(self, value):
                return EnrichmentResult(value, (reference_bundle,), ())

        class StubAtlas:
            def retrieve(self, callback_variant, context):
                return _replayable_atlas_bundle(
                    callback_variant,
                    context,
                    reference_bundle,
                )

        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(
                directory,
                reference_retriever=StubRetriever(),
                atlas_retriever=StubAtlas(),
            )
            dossier = runtime.evaluate(manifest, live_reference=True)
            snapshot = runtime.load_run_snapshot(dossier.run_id)
            events = snapshot.event_log.all()
            atlas_event = next(
                event for event in events if event.event_type == "public_atlas_collected"
            )
            original_payload = dict(atlas_event.payload)
            original_replay_address = original_payload["replay_input_addresses"][0]
            original_bundle_address = original_payload["bundle_addresses"][0]
            substituted_bundle = PublicAtlasRetriever().retrieve(
                variant,
                manifest.context,
                query=AtlasQuery(variant_id=variant.variant_id, window_bp=1_999),
                reference_bundle=reference_bundle,
            )
            substituted_replay_address = runtime.store.store.put(
                substituted_bundle.replay_inputs.to_dict()
            )
            substituted_bundle_address = runtime.store.store.put(substituted_bundle.to_dict())
            cases = (
                (
                    "replay_input_addresses",
                    "sha256:" + "0" * 64,
                    "missing or invalid",
                ),
                (
                    "replay_input_addresses",
                    substituted_replay_address,
                    "exact replay inputs",
                ),
                (
                    "bundle_addresses",
                    substituted_bundle_address,
                    "exact replay inputs",
                ),
            )
            for field_name, replacement_address, expected_error in cases:
                with self.subTest(field=field_name, expected_error=expected_error):
                    payload = dict(original_payload)
                    payload[field_name] = [replacement_address]
                    replaced_address = (
                        original_replay_address
                        if field_name == "replay_input_addresses"
                        else original_bundle_address
                    )
                    altered_dossier = replace(
                        snapshot.dossier,
                        source_bundle_addresses=tuple(
                            replacement_address if address == replaced_address else address
                            for address in snapshot.dossier.source_bundle_addresses
                        ),
                    )
                    altered_log = EventLog(dossier.run_id)
                    for event in events:
                        altered_log.append(
                            event.event_type,
                            (
                                payload
                                if event.event_type == "public_atlas_collected"
                                else event.payload
                            ),
                            event_id=event.event_id,
                        )
                    with self.assertRaisesRegex(ValidationError, expected_error):
                        runtime._validate_persisted_source_closure(  # noqa: SLF001
                            manifest=snapshot.manifest,
                            dossier=altered_dossier,
                            events=altered_log.all(),
                            rna_address=None,
                        )

    def test_atlas_callback_reserves_both_pair_slots_before_invocation(self) -> None:
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
        atlas_calls: list[str] = []

        class StubRetriever:
            def enrich_manifest(self, value):
                return EnrichmentResult(value, (reference_bundle,), ())

        class ForbiddenAtlas:
            def retrieve(self, variant, context):
                atlas_calls.append(variant.variant_id)
                raise AssertionError("atlas callback ran with only one pair slot available")

        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(
                directory,
                reference_retriever=StubRetriever(),
                atlas_retriever=ForbiddenAtlas(),
            )
            runtime.validator = ContractValidator(
                limits=replace(runtime.validator.limits, max_source_bundles=3)
            )
            with self.assertRaisesRegex(
                ValidationError,
                "source_bundle_addresses.*maximum of 3",
            ):
                runtime.evaluate(manifest, live_reference=True)
            self.assertEqual(atlas_calls, [])
            self.assertEqual(tuple(runtime.store.store.objects.glob("*.json")), ())

    def test_atlas_callbacks_are_detached_and_mutation_fails_before_publication(self) -> None:
        manifest = fixture_manifest()
        original = manifest.to_dict()
        reference_bundle = ReferenceBundle.create(
            variant_id=manifest.variants[0].variant_id,
            context=manifest.context,
            sequence=None,
            elements=(),
            raw_features=(),
            receipts=(),
            warnings=(),
        )

        class StubRetriever:
            def enrich_manifest(self, value):
                return EnrichmentResult(value, (reference_bundle,), ())

        class MutatingAtlas:
            def retrieve(self, variant, context):
                object.__setattr__(variant, "sample_id", "poisoned-atlas-input")
                return _replayable_atlas_bundle(
                    variant,
                    context,
                    reference_bundle,
                )

        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(
                directory,
                reference_retriever=StubRetriever(),
                atlas_retriever=MutatingAtlas(),
            )
            with self.assertRaisesRegex(ValidationError, "mutated its callback inputs"):
                runtime.evaluate(manifest, live_reference=True)
            self.assertEqual(manifest.to_dict(), original)
            self.assertEqual(tuple(runtime.store.store.objects.glob("*.json")), ())
            self.assertEqual(tuple(runtime.store.runs.glob("*.json")), ())

    def test_source_budget_stops_later_atlas_callbacks(self) -> None:
        base = fixture_manifest()
        second_variant = replace(
            base.variants[0],
            variant_id="variant-fixture-002",
            start=base.variants[0].start + 50,
            end=base.variants[0].end + 50,
        )
        manifest = replace(base, variants=(base.variants[0], second_variant))
        reference_bundles = tuple(
            ReferenceBundle.create(
                variant_id=variant.variant_id,
                context=manifest.context,
                sequence=None,
                elements=(),
                raw_features=(),
                receipts=(),
                warnings=(),
            )
            for variant in manifest.variants
        )
        reference_by_variant = {bundle.variant_id: bundle for bundle in reference_bundles}

        def atlas_bundle(variant, context):
            return _replayable_atlas_bundle(
                variant,
                context,
                reference_by_variant[variant.variant_id],
            )

        first_atlas_bundle = atlas_bundle(manifest.variants[0], manifest.context)
        first_atlas_record = first_atlas_bundle.to_dict()
        first_replay_record = first_atlas_bundle.replay_inputs.to_dict()
        base_byte_limit = (
            len(canonical_bytes(manifest.to_dict()))
            + sum(len(canonical_bytes(bundle.to_dict())) for bundle in reference_bundles)
        )
        byte_limit = (
            base_byte_limit
            + len(canonical_bytes(first_replay_record))
            + len(canonical_bytes(first_atlas_record))
        )
        atlas_calls: list[str] = []

        class StubRetriever:
            def enrich_manifest(self, value):
                return EnrichmentResult(value, reference_bundles, ())

        class BoundedAtlas:
            def retrieve(self, variant, context):
                atlas_calls.append(variant.variant_id)
                if len(atlas_calls) > 1:
                    raise AssertionError("later atlas callback ran after budget exhaustion")
                return atlas_bundle(variant, context)

        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(
                directory,
                reference_retriever=StubRetriever(),
                atlas_retriever=BoundedAtlas(),
                source_closure_max_bytes=base_byte_limit,
            )
            with self.assertRaisesRegex(ValidationError, "aggregate canonical byte ceiling"):
                runtime.evaluate(manifest, live_reference=True)
            self.assertEqual(atlas_calls, [])
            self.assertEqual(tuple(runtime.store.store.objects.glob("*.json")), ())

        atlas_calls.clear()
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(
                directory,
                reference_retriever=StubRetriever(),
                atlas_retriever=BoundedAtlas(),
            )
            runtime.validator = ContractValidator(
                limits=replace(runtime.validator.limits, max_source_bundles=3)
            )
            with self.assertRaisesRegex(
                ValidationError,
                "source_bundle_addresses.*maximum of 3",
            ):
                runtime.evaluate(manifest, live_reference=True)
            self.assertEqual(atlas_calls, [])
            self.assertEqual(tuple(runtime.store.store.objects.glob("*.json")), ())

        atlas_calls.clear()
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(
                directory,
                reference_retriever=StubRetriever(),
                atlas_retriever=BoundedAtlas(),
                source_closure_max_bytes=byte_limit,
            )
            with self.assertRaisesRegex(ValidationError, "aggregate canonical byte ceiling"):
                runtime.evaluate(manifest, live_reference=True)
            self.assertEqual(atlas_calls, [manifest.variants[0].variant_id])
            self.assertEqual(tuple(runtime.store.store.objects.glob("*.json")), ())

    def test_combined_receipt_limit_stops_later_atlas_callbacks(self) -> None:
        base = fixture_manifest()
        second_variant = replace(
            base.variants[0],
            variant_id="variant-receipt-limit-002",
            start=base.variants[0].start + 50,
            end=base.variants[0].end + 50,
        )
        manifest = replace(base, variants=(base.variants[0], second_variant))
        reference_bundles = tuple(
            ReferenceBundle.create(
                variant_id=variant.variant_id,
                context=manifest.context,
                sequence=None,
                elements=(),
                raw_features=(),
                receipts=((_receipt("reference"),) if index == 0 else ()),
                warnings=(),
            )
            for index, variant in enumerate(manifest.variants)
        )
        reference_by_variant = {bundle.variant_id: bundle for bundle in reference_bundles}
        atlas_calls: list[str] = []

        class StubRetriever:
            def enrich_manifest(self, value):
                return EnrichmentResult(value, reference_bundles, ())

        class BoundedAtlas:
            def retrieve(self, variant, context):
                atlas_calls.append(variant.variant_id)
                if len(atlas_calls) > 1:
                    raise AssertionError("later atlas callback ran after receipt exhaustion")
                return _replayable_atlas_bundle(
                    variant,
                    context,
                    reference_by_variant[variant.variant_id],
                )

        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(
                directory,
                reference_retriever=StubRetriever(),
                atlas_retriever=BoundedAtlas(),
            )
            runtime.validator = ContractValidator(
                limits=replace(runtime.validator.limits, max_source_receipts=2)
            )
            with self.assertRaisesRegex(ValidationError, "source_receipts.*maximum of 2"):
                runtime.evaluate(manifest, live_reference=True)
            self.assertEqual(atlas_calls, [manifest.variants[0].variant_id])
            self.assertEqual(tuple(runtime.store.store.objects.glob("*.json")), ())

    def test_sequence_limit_also_gates_progressive_source_receipts(self) -> None:
        base = fixture_manifest()
        second_variant = replace(
            base.variants[0],
            variant_id="variant-sequence-receipt-limit-002",
            start=base.variants[0].start + 50,
            end=base.variants[0].end + 50,
        )
        manifest = replace(base, variants=(base.variants[0], second_variant))
        reference_bundles = tuple(
            ReferenceBundle.create(
                variant_id=variant.variant_id,
                context=manifest.context,
                sequence=None,
                elements=(),
                raw_features=(),
                receipts=(
                    tuple(_receipt(f"reference-{item}") for item in range(9))
                    if index == 0
                    else ()
                ),
                warnings=(),
            )
            for index, variant in enumerate(manifest.variants)
        )
        reference_by_variant = {bundle.variant_id: bundle for bundle in reference_bundles}
        atlas_calls: list[str] = []

        class StubRetriever:
            def enrich_manifest(self, value):
                return EnrichmentResult(value, reference_bundles, ())

        class BoundedAtlas:
            def retrieve(self, variant, context):
                atlas_calls.append(variant.variant_id)
                if len(atlas_calls) > 1:
                    raise AssertionError("later atlas callback ran after sequence exhaustion")
                return _replayable_atlas_bundle(
                    variant,
                    context,
                    reference_by_variant[variant.variant_id],
                )

        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(
                directory,
                reference_retriever=StubRetriever(),
                atlas_retriever=BoundedAtlas(),
            )
            runtime.validator = ContractValidator(
                limits=replace(runtime.validator.limits, max_sequence_items=10)
            )
            with self.assertRaisesRegex(ValidationError, "source_receipts.*maximum of 10"):
                runtime.evaluate(manifest, live_reference=True)
            self.assertEqual(atlas_calls, [manifest.variants[0].variant_id])
            self.assertEqual(tuple(runtime.store.store.objects.glob("*.json")), ())

    def test_sequence_limit_also_gates_persisted_source_receipts(self) -> None:
        manifest = fixture_manifest()
        reference_bundle = ReferenceBundle.create(
            variant_id=manifest.variants[0].variant_id,
            context=manifest.context,
            sequence=None,
            elements=(),
            raw_features=(),
            receipts=tuple(_receipt(f"persisted-reference-{item}") for item in range(101)),
            warnings=(),
        )

        class StubRetriever:
            def enrich_manifest(self, value):
                return EnrichmentResult(value, (reference_bundle,), ())

        with tempfile.TemporaryDirectory() as directory:
            writer = CaseRuntime(directory, reference_retriever=StubRetriever())
            dossier = writer.evaluate(manifest, live_reference=True)
            self.assertEqual(len(dossier.source_receipts), 101)

            reader = CaseRuntime(directory)
            reader.validator = ContractValidator(
                limits=replace(reader.validator.limits, max_sequence_items=100)
            )
            with self.assertRaisesRegex(
                ValidationError,
                "persisted source_receipts.*maximum of 100",
            ):
                reader.load_dossier(dossier.content_address)
            with self.assertRaisesRegex(
                ValidationError,
                "persisted source_receipts.*maximum of 100",
            ):
                reader.load_run_snapshot(dossier.run_id)

    def test_atlas_claim_limit_stops_later_eligible_callbacks(self) -> None:
        base = fixture_manifest()
        second_variant = replace(
            base.variants[0],
            variant_id="variant-claim-limit-002",
        )
        manifest = replace(base, variants=(base.variants[0], second_variant))
        reference_bundles = tuple(
            ReferenceBundle.create(
                variant_id=variant.variant_id,
                context=manifest.context,
                sequence=None,
                elements=(),
                raw_features=(),
                receipts=(),
                warnings=(),
            )
            for variant in manifest.variants
        )
        reference_by_variant = {bundle.variant_id: bundle for bundle in reference_bundles}
        atlas_calls: list[str] = []

        class StubRetriever:
            def enrich_manifest(self, value):
                return EnrichmentResult(value, reference_bundles, ())

        class BoundedAtlas:
            def retrieve(self, variant, context):
                atlas_calls.append(variant.variant_id)
                if len(atlas_calls) > 1:
                    raise AssertionError("later atlas callback ran after claim exhaustion")
                return _replayable_atlas_bundle(
                    variant,
                    context,
                    reference_by_variant[variant.variant_id],
                )

        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(
                directory,
                reference_retriever=StubRetriever(),
                atlas_retriever=BoundedAtlas(),
                hypothesis_limits=HypothesisWorkLimits(max_external_claims=2),
            )
            with self.assertRaisesRegex(ValidationError, "external_claims.*maximum of 2"):
                runtime.evaluate(manifest, live_reference=True)
            self.assertEqual(atlas_calls, [manifest.variants[0].variant_id])
            self.assertEqual(tuple(runtime.store.store.objects.glob("*.json")), ())

    def test_validator_claim_headroom_gates_atlas_before_callback(self) -> None:
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
        atlas_calls: list[str] = []

        class StubRetriever:
            def enrich_manifest(self, value):
                return EnrichmentResult(value, (reference_bundle,), ())

        class ForbiddenAtlas:
            def retrieve(self, variant, context):
                atlas_calls.append(variant.variant_id)
                raise AssertionError("atlas callback ran without evidence claim headroom")

        with tempfile.TemporaryDirectory() as directory:
            probe = CaseRuntime(directory)
            native = probe.builder.build(
                manifest,
                probe._run_id(manifest),  # noqa: SLF001
            ).claims
        native_by_edge: dict[str, int] = {}
        for claim in native:
            native_by_edge[claim.edge_id] = native_by_edge.get(claim.edge_id, 0) + 1
        variant = manifest.variants[0]
        element = min(
            probe.builder._eligible_elements(  # noqa: SLF001
                variant,
                manifest.candidate_elements,
            ),
            key=lambda item: (
                -runtime_module.element_relevance(variant, item)[0],
                item.element_id,
            ),
        )
        selected_edge = probe.builder._edge_id(  # noqa: SLF001
            variant.variant_id,
            element.element_id,
            runtime_module.EdgeType.VARIANT_TO_ELEMENT,
        )
        selected_native_count = native_by_edge[selected_edge]
        self.assertGreaterEqual(selected_native_count, max(native_by_edge.values()))

        for label, updates, message in (
            (
                "total",
                {"max_evidence_claims": len(native)},
                "external_claims.*maximum of 0",
            ),
            (
                "per edge",
                {"max_claims_per_edge": selected_native_count},
                "external_claims.*per-edge maximum",
            ),
        ):
            with self.subTest(label=label), tempfile.TemporaryDirectory() as directory:
                runtime = CaseRuntime(
                    directory,
                    reference_retriever=StubRetriever(),
                    atlas_retriever=ForbiddenAtlas(),
                )
                runtime.validator = ContractValidator(
                    limits=replace(runtime.validator.limits, **updates)
                )
                with self.assertRaisesRegex(ValidationError, message):
                    runtime.evaluate(manifest, live_reference=True)
                self.assertEqual(atlas_calls, [])
                self.assertEqual(tuple(runtime.store.store.objects.glob("*.json")), ())

    def test_warning_limit_stops_atlas_callbacks_after_the_crossing_bundle(self) -> None:
        base = fixture_manifest()
        reference_warnings = tuple(
            f"reference warning before atlas capacity accounting {index}"
            for index in range(8)
        )
        variants = (
            base.variants[0],
            replace(
                base.variants[0],
                variant_id="variant-warning-limit-002",
                start=base.variants[0].start + 1,
                end=base.variants[0].end + 1,
            ),
            replace(
                base.variants[0],
                variant_id="variant-warning-limit-003",
                start=base.variants[0].start + 2,
                end=base.variants[0].end + 2,
            ),
        )
        manifest = replace(base, variants=variants)
        reference_bundles = tuple(
            ReferenceBundle.create(
                variant_id=variant.variant_id,
                context=manifest.context,
                sequence=None,
                elements=(),
                raw_features=(),
                receipts=(),
                warnings=(reference_warnings if index == 0 else ()),
            )
            for index, variant in enumerate(manifest.variants)
        )
        reference_by_variant = {bundle.variant_id: bundle for bundle in reference_bundles}
        atlas_calls: list[str] = []

        class StubRetriever:
            def enrich_manifest(self, value):
                return EnrichmentResult(value, reference_bundles, reference_warnings)

        class WarningAtlas:
            def retrieve(self, variant, context):
                atlas_calls.append(variant.variant_id)
                if len(atlas_calls) > 2:
                    raise AssertionError("atlas callback continued after warning overflow")
                return _replayable_atlas_bundle(
                    variant,
                    context,
                    reference_by_variant[variant.variant_id],
                    atlas_warning=f"warning for {variant.variant_id}",
                )

        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(
                directory,
                reference_retriever=StubRetriever(),
                atlas_retriever=WarningAtlas(),
            )
            runtime.validator = ContractValidator(
                limits=replace(runtime.validator.limits, max_sequence_items=10)
            )
            with self.assertRaisesRegex(ValidationError, "warnings.*maximum of 10"):
                runtime.evaluate(manifest, live_reference=True)
            self.assertEqual(
                atlas_calls,
                [manifest.variants[0].variant_id, manifest.variants[1].variant_id],
            )
            self.assertEqual(tuple(runtime.store.store.objects.glob("*.json")), ())

    def test_reference_warning_overflow_stops_atlas_before_its_first_callback(self) -> None:
        manifest = fixture_manifest()
        reference_warnings = tuple(f"reference warning {index}" for index in range(11))
        reference_bundle = ReferenceBundle.create(
            variant_id=manifest.variants[0].variant_id,
            context=manifest.context,
            sequence=None,
            elements=(),
            raw_features=(),
            receipts=(),
            warnings=reference_warnings,
        )
        atlas_calls: list[str] = []

        class StubRetriever:
            def enrich_manifest(self, value):
                return EnrichmentResult(value, (reference_bundle,), reference_warnings)

        class ForbiddenAtlas:
            def retrieve(self, variant, context):
                atlas_calls.append(variant.variant_id)
                raise AssertionError("atlas callback ran after reference warning overflow")

        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(
                directory,
                reference_retriever=StubRetriever(),
                atlas_retriever=ForbiddenAtlas(),
            )
            runtime.validator = ContractValidator(
                limits=replace(runtime.validator.limits, max_sequence_items=10)
            )
            with self.assertRaisesRegex(ValidationError, "warnings.*maximum of 10"):
                runtime.evaluate(manifest, live_reference=True)
            self.assertEqual(atlas_calls, [])
            self.assertEqual(tuple(runtime.store.store.objects.glob("*.json")), ())

    def test_reference_event_byte_overflow_stops_atlas_before_its_first_callback(self) -> None:
        manifest = fixture_manifest()
        warnings = ("wide reference warning " + "\U0001f9e0" * 100,)
        reference_bundle = ReferenceBundle.create(
            variant_id=manifest.variants[0].variant_id,
            context=manifest.context,
            sequence=None,
            elements=(),
            raw_features=(),
            receipts=(),
            warnings=warnings,
        )
        atlas_calls: list[str] = []

        class StubRetriever:
            def enrich_manifest(self, value):
                return EnrichmentResult(value, (reference_bundle,), warnings)

        class ForbiddenAtlas:
            def retrieve(self, variant, context):
                atlas_calls.append(variant.variant_id)
                raise AssertionError("atlas callback ran after reference event overflow")

        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(
                directory,
                reference_retriever=StubRetriever(),
                atlas_retriever=ForbiddenAtlas(),
            )
            with (
                patch.object(runtime_module, "MAX_EVENT_PAYLOAD_BYTES", 350),
                self.assertRaisesRegex(
                    ValidationError,
                    "public reference event payload exceeds.*350 bytes",
                ),
            ):
                runtime.evaluate(manifest, live_reference=True)
            self.assertEqual(atlas_calls, [])
            self.assertEqual(tuple(runtime.store.store.objects.glob("*.json")), ())

    def test_reference_bundle_slots_are_reserved_before_retrieval(self) -> None:
        base = fixture_manifest()
        second_variant = replace(
            base.variants[0],
            variant_id="variant-reference-slot-002",
            start=base.variants[0].start + 50,
            end=base.variants[0].end + 50,
        )
        manifest = replace(base, variants=(base.variants[0], second_variant))
        calls: list[str] = []

        class ForbiddenRetriever:
            def enrich_manifest(self, value):
                calls.append(value.case_id)
                raise AssertionError("reference callback ran without mandatory bundle slots")

        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory, reference_retriever=ForbiddenRetriever())
            runtime.validator = ContractValidator(
                limits=replace(runtime.validator.limits, max_source_bundles=2)
            )
            with self.assertRaisesRegex(
                ValidationError,
                "source_bundle_addresses.*maximum of 2",
            ):
                runtime.evaluate(manifest, live_reference=True)
            self.assertEqual(calls, [])
            self.assertEqual(tuple(runtime.store.store.objects.glob("*.json")), ())

    def test_atlas_event_reserves_the_next_mandatory_address(self) -> None:
        base = fixture_manifest()
        second_variant = replace(
            base.variants[0],
            variant_id="variant-atlas-event-address-002",
            start=base.variants[0].start + 50,
            end=base.variants[0].end + 50,
        )
        manifest = replace(base, variants=(base.variants[0], second_variant))
        reference_bundles = tuple(
            ReferenceBundle.create(
                variant_id=variant.variant_id,
                context=manifest.context,
                sequence=None,
                elements=(),
                raw_features=(),
                receipts=(),
                warnings=(),
            )
            for variant in manifest.variants
        )
        reference_by_variant = {bundle.variant_id: bundle for bundle in reference_bundles}
        atlas_calls: list[str] = []

        class StubRetriever:
            def enrich_manifest(self, value):
                return EnrichmentResult(value, reference_bundles, ())

        class BoundedAtlas:
            def retrieve(self, variant, context):
                atlas_calls.append(variant.variant_id)
                if len(atlas_calls) > 1:
                    raise AssertionError("atlas callback ran without event address capacity")
                return _replayable_atlas_bundle(
                    variant,
                    context,
                    reference_by_variant[variant.variant_id],
                    atlas_warning="atlas event padding " + "x" * 500,
                )

        first_bundle = _replayable_atlas_bundle(
            manifest.variants[0],
            manifest.context,
            reference_bundles[0],
            atlas_warning="atlas event padding " + "x" * 500,
        )
        one_bundle_event_bytes = len(
            canonical_bytes(
                {
                    "replay_input_addresses": [first_bundle.replay_inputs.content_address],
                    "bundle_addresses": [first_bundle.content_address],
                    "claim_count": len(first_bundle.observations),
                    "warnings": list(first_bundle.warnings),
                }
            )
        )
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(
                directory,
                reference_retriever=StubRetriever(),
                atlas_retriever=BoundedAtlas(),
            )
            with (
                patch.object(
                    runtime_module,
                    "MAX_EVENT_PAYLOAD_BYTES",
                    one_bundle_event_bytes,
                ),
                self.assertRaisesRegex(
                    ValidationError,
                    "public atlas event payload exceeds",
                ),
            ):
                runtime.evaluate(manifest, live_reference=True)
            self.assertEqual(atlas_calls, [manifest.variants[0].variant_id])
            self.assertEqual(tuple(runtime.store.store.objects.glob("*.json")), ())

    def test_atlas_warning_exhaustion_stops_the_next_callback(self) -> None:
        base = fixture_manifest()
        reference_warnings = tuple(
            f"reference warning before atlas capacity accounting {index}"
            for index in range(9)
        )
        second_variant = replace(
            base.variants[0],
            variant_id="variant-atlas-warning-capacity-002",
            start=base.variants[0].start + 50,
            end=base.variants[0].end + 50,
        )
        manifest = replace(base, variants=(base.variants[0], second_variant))
        reference_bundles = tuple(
            ReferenceBundle.create(
                variant_id=variant.variant_id,
                context=manifest.context,
                sequence=None,
                elements=(),
                raw_features=(),
                receipts=(),
                warnings=(reference_warnings if index == 0 else ()),
            )
            for index, variant in enumerate(manifest.variants)
        )
        reference_by_variant = {bundle.variant_id: bundle for bundle in reference_bundles}
        atlas_calls: list[str] = []

        class StubRetriever:
            def enrich_manifest(self, value):
                return EnrichmentResult(value, reference_bundles, reference_warnings)

        class WarningAtlas:
            def retrieve(self, variant, context):
                atlas_calls.append(variant.variant_id)
                if len(atlas_calls) > 1:
                    raise AssertionError("atlas callback ran after warning exhaustion")
                return _replayable_atlas_bundle(
                    variant,
                    context,
                    reference_by_variant[variant.variant_id],
                    atlas_warning="available warning slot",
                )

        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(
                directory,
                reference_retriever=StubRetriever(),
                atlas_retriever=WarningAtlas(),
            )
            runtime.validator = ContractValidator(
                limits=replace(runtime.validator.limits, max_sequence_items=10)
            )
            with self.assertRaisesRegex(ValidationError, "warnings.*maximum of 10"):
                runtime.evaluate(manifest, live_reference=True)
            self.assertEqual(atlas_calls, [manifest.variants[0].variant_id])
            self.assertEqual(tuple(runtime.store.store.objects.glob("*.json")), ())

    def test_event_byte_limit_stops_atlas_callbacks_after_the_crossing_bundle(self) -> None:
        base = fixture_manifest()
        variants = tuple(
            replace(
                base.variants[0],
                variant_id=f"variant-event-limit-{index:03d}",
                start=base.variants[0].start + index,
                end=base.variants[0].end + index,
            )
            for index in range(3)
        )
        manifest = replace(base, variants=variants)
        reference_bundles = tuple(
            ReferenceBundle.create(
                variant_id=variant.variant_id,
                context=manifest.context,
                sequence=None,
                elements=(),
                raw_features=(),
                receipts=(),
                warnings=(),
            )
            for variant in manifest.variants
        )
        reference_by_variant = {bundle.variant_id: bundle for bundle in reference_bundles}
        atlas_calls: list[str] = []
        first_warning = "first atlas event padding " + "x" * 500

        class StubRetriever:
            def enrich_manifest(self, value):
                return EnrichmentResult(value, reference_bundles, ())

        class WarningAtlas:
            def retrieve(self, variant, context):
                atlas_calls.append(variant.variant_id)
                if len(atlas_calls) > 2:
                    raise AssertionError("atlas callback continued after event overflow")
                return _replayable_atlas_bundle(
                    variant,
                    context,
                    reference_by_variant[variant.variant_id],
                    atlas_warning=(
                        first_warning
                        if variant.variant_id == manifest.variants[0].variant_id
                        else f"{variant.variant_id}:" + "x" * 200
                    ),
                )

        first_bundle = _replayable_atlas_bundle(
            manifest.variants[0],
            manifest.context,
            reference_bundles[0],
            atlas_warning=first_warning,
        )
        event_limit = len(
            canonical_bytes(
                {
                    "replay_input_addresses": [
                        first_bundle.replay_inputs.content_address,
                        "sha256:" + "0" * 64,
                    ],
                    "bundle_addresses": [
                        first_bundle.content_address,
                        "sha256:" + "0" * 64,
                    ],
                    "claim_count": len(first_bundle.observations),
                    "warnings": list(first_bundle.warnings),
                }
            )
        )

        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(
                directory,
                reference_retriever=StubRetriever(),
                atlas_retriever=WarningAtlas(),
            )
            with (
                patch.object(runtime_module, "MAX_EVENT_PAYLOAD_BYTES", event_limit),
                self.assertRaisesRegex(
                    ValidationError,
                    f"public atlas event payload exceeds.*{event_limit} bytes",
                ),
            ):
                runtime.evaluate(manifest, live_reference=True)
            self.assertEqual(
                atlas_calls,
                [manifest.variants[0].variant_id, manifest.variants[1].variant_id],
            )
            self.assertEqual(tuple(runtime.store.store.objects.glob("*.json")), ())

    def test_atlas_claim_limit_is_checked_before_claim_expansion(self) -> None:
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
        observations = tuple(
            AtlasObservation(
                observation_id=f"atlas-limit-{index}",
                source_id="SRC-ENSEMBL-REST",
                feature_type="reference_annotation",
                state=EvidenceState.SUPPORTED,
                tier=EvidenceTier.REFERENCE,
                summary=f"bounded public observation {index}",
                payload={"index": index},
                context_key=manifest.context.key,
                context_score=None,
                receipt=None,
            )
            for index in range(2)
        )

        class StubRetriever:
            def enrich_manifest(self, value):
                return EnrichmentResult(value, (reference_bundle,), ())

        class StubAtlas:
            def retrieve(self, variant, context):
                return oversized_bundle

        replayable = _replayable_atlas_bundle(
            manifest.variants[0],
            manifest.context,
            reference_bundle,
        )
        oversized_bundle = AtlasBundle.create(
            variant=manifest.variants[0],
            context=manifest.context,
            query=AtlasQuery(variant_id=manifest.variants[0].variant_id),
            source_bundle_address=reference_bundle.content_address,
            replay_inputs=replayable.replay_inputs,
            observations=observations,
            receipts=(),
            warnings=(),
        )

        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(
                directory,
                reference_retriever=StubRetriever(),
                atlas_retriever=StubAtlas(),
                hypothesis_limits=HypothesisWorkLimits(max_external_claims=1),
            )
            with (
                patch.object(
                    AtlasBundle,
                    "to_dict",
                    side_effect=AssertionError("atlas bundle expanded past configured limit"),
                ),
                patch.object(
                    AtlasBundle,
                    "to_evidence_claims",
                    side_effect=AssertionError("atlas claims expanded past configured limit"),
                ),
                self.assertRaisesRegex(ValidationError, "external_claims.*maximum of 1"),
            ):
                runtime.evaluate(manifest, live_reference=True)
            self.assertEqual(tuple(runtime.store.store.objects.glob("*.json")), ())

    def test_untrusted_callbacks_cannot_change_runtime_configuration_mid_evaluation(self) -> None:
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

        class StubRetriever:
            def enrich_manifest(self, value):
                return EnrichmentResult(value, (reference_bundle,), ())

        class MutatingAtlas:
            def __init__(self, mutate):
                self.mutate = mutate
                self.runtime = None

            def retrieve(self, variant, context):
                assert self.runtime is not None
                self.mutate(self.runtime)
                return _replayable_atlas_bundle(
                    variant,
                    context,
                    reference_bundle,
                )

        def configure_validator(runtime):
            runtime.validator = ContractValidator(
                limits=replace(runtime.validator.limits, max_evidence_claims=1_000)
            )

        cases = (
            (
                "builder limits",
                lambda runtime: None,
                lambda runtime: setattr(
                    runtime.builder,
                    "limits",
                    HypothesisWorkLimits(max_external_claims=2),
                ),
            ),
            (
                "validator identity",
                configure_validator,
                lambda runtime: setattr(runtime, "validator", ContractValidator()),
            ),
            (
                "planner limits",
                lambda runtime: None,
                lambda runtime: setattr(
                    runtime.planner,
                    "limits",
                    ExperimentPlanningLimits(max_hypotheses=2),
                ),
            ),
            (
                "source closure ceiling",
                lambda runtime: None,
                lambda runtime: setattr(
                    runtime,
                    "_source_closure_max_bytes",
                    runtime.source_closure_max_bytes - 1,
                ),
            ),
            (
                "policy limits",
                lambda runtime: None,
                lambda runtime: setattr(
                    runtime.policy,
                    "limits",
                    PolicyLimits(max_text_items=1),
                ),
            ),
            (
                "release validator",
                lambda runtime: None,
                lambda runtime: setattr(
                    runtime.release_gate,
                    "validator",
                    ContractValidator(),
                ),
            ),
        )
        for label, configure, mutate in cases:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as directory:
                atlas = MutatingAtlas(mutate)
                runtime = CaseRuntime(
                    directory,
                    reference_retriever=StubRetriever(),
                    atlas_retriever=atlas,
                    hypothesis_limits=HypothesisWorkLimits(max_external_claims=1),
                )
                configure(runtime)
                atlas.runtime = runtime
                expected_configuration = runtime._capture_evaluation_configuration()  # noqa: SLF001
                with self.assertRaisesRegex(
                    ValidationError,
                    "runtime evaluation configuration changed",
                ):
                    runtime.evaluate(manifest, live_reference=True)
                runtime._assert_evaluation_configuration(  # noqa: SLF001
                    expected_configuration
                )
                self.assertEqual(tuple(runtime.store.store.objects.glob("*.json")), ())
                self.assertEqual(tuple(runtime.store.runs.glob("*.json")), ())
                self.assertEqual(runtime.evaluate(manifest).case_id, manifest.case_id)

    def test_rna_iterator_cannot_change_runtime_configuration(self) -> None:
        manifest = fixture_manifest()
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            original_planner = runtime.planner
            original_limits = runtime.planner.limits

            def mutating_rows():
                runtime.planner.limits = ExperimentPlanningLimits(max_hypotheses=1)
                if False:
                    yield None

            with self.assertRaisesRegex(
                ValidationError,
                "runtime evaluation configuration changed",
            ):
                runtime.evaluate(manifest, rna_consequences=mutating_rows())
            self.assertIs(runtime.planner, original_planner)
            self.assertIs(runtime.planner.limits, original_limits)
            self.assertEqual(runtime.planner.limits, ExperimentPlanningLimits())
            self.assertEqual(tuple(runtime.store.store.objects.glob("*.json")), ())
            self.assertEqual(tuple(runtime.store.runs.glob("*.json")), ())
            self.assertEqual(runtime.evaluate(manifest).case_id, manifest.case_id)

    def test_callback_exception_and_invalid_mutation_restore_configuration(self) -> None:
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

        for label, mutate in (
            (
                "valid replacement",
                lambda runtime: setattr(
                    runtime.builder,
                    "limits",
                    HypothesisWorkLimits(max_work_items=1),
                ),
            ),
            (
                "deleted limits",
                lambda runtime: delattr(runtime.planner, "limits"),
            ),
        ):
            with self.subTest(label=label), tempfile.TemporaryDirectory() as directory:
                class FailingOnceRetriever:
                    def __init__(self, mutation) -> None:
                        self.calls = 0
                        self.runtime = None
                        self.mutation = mutation

                    def enrich_manifest(self, value):
                        self.calls += 1
                        if self.calls == 1:
                            assert self.runtime is not None
                            self.mutation(self.runtime)
                            raise RuntimeError("fixture callback failure")
                        return EnrichmentResult(value, (reference_bundle,), ())

                retriever = FailingOnceRetriever(mutate)
                runtime = CaseRuntime(directory, reference_retriever=retriever)
                retriever.runtime = runtime
                expected_configuration = runtime._capture_evaluation_configuration()  # noqa: SLF001
                with self.assertRaisesRegex(RuntimeError, "fixture callback failure"):
                    runtime.evaluate(manifest, live_reference=True)
                runtime._assert_evaluation_configuration(  # noqa: SLF001
                    expected_configuration
                )
                dossier = runtime.evaluate(manifest, live_reference=True)
                self.assertEqual(dossier.case_id, manifest.case_id)

    def test_reference_callback_cannot_recursively_enter_the_same_runtime(self) -> None:
        manifest = fixture_manifest()

        class RecursiveRetriever:
            def __init__(self) -> None:
                self.runtime = None
                self.calls = 0

            def enrich_manifest(self, value):
                self.calls += 1
                assert self.runtime is not None
                return self.runtime.evaluate(value)

        retriever = RecursiveRetriever()
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory, reference_retriever=retriever)
            retriever.runtime = runtime
            with self.assertRaisesRegex(
                ValidationError,
                "recursive runtime evaluation is not supported",
            ):
                runtime.evaluate(manifest, live_reference=True)
            self.assertEqual(retriever.calls, 1)
            self.assertEqual(tuple(runtime.store.store.objects.glob("*.json")), ())
            self.assertEqual(tuple(runtime.store.runs.glob("*.json")), ())

    def test_reference_callback_cannot_tamper_with_recursive_evaluation_guard(self) -> None:
        manifest = fixture_manifest()
        nested_manifest = replace(manifest, case_id="case-recursive-side-run")

        class TamperingRecursiveRetriever:
            def __init__(self) -> None:
                self.runtime = None
                self.calls = 0

            def enrich_manifest(self, value):
                self.calls += 1
                assert self.runtime is not None
                self.runtime._evaluation_active = False  # noqa: SLF001
                return self.runtime.evaluate(nested_manifest)

        retriever = TamperingRecursiveRetriever()
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory, reference_retriever=retriever)
            retriever.runtime = runtime
            with self.assertRaisesRegex(
                ValidationError,
                "recursive runtime evaluation is not supported",
            ):
                runtime.evaluate(manifest, live_reference=True)
            self.assertEqual(retriever.calls, 1)
            self.assertFalse(runtime._evaluation_active)  # noqa: SLF001
            self.assertEqual(tuple(runtime.store.store.objects.glob("*.json")), ())
            self.assertEqual(tuple(runtime.store.runs.glob("*.json")), ())
            self.assertEqual(runtime.evaluate(manifest).case_id, manifest.case_id)

    def test_adapter_replay_rejects_attribution_overflow_before_item_iteration(self) -> None:
        version_keys = (
            "adapter_input_manifest",
            "adapter_registry_snapshot",
            "adapter_resolution_report",
            "adapter_claim_collection_report",
        )
        source_addresses = tuple(f"sha256:{index:064x}" for index in range(1, 5))
        manifest = replace(
            fixture_manifest(),
            input_versions=dict(zip(version_keys, source_addresses, strict=True)),
        )
        records = {address: {} for address in source_addresses}
        records[source_addresses[-1]] = {"attributions": [{}] * 100_001}
        event = SimpleNamespace(
            payload={
                "adapter_ids": [],
                "base_input_address": source_addresses[0],
                "effective_input_address": manifest.content_address,
                "registry_bundle_address": source_addresses[1],
                "registry_address": "adapter-registry:" + "0" * 64,
                "resolution_bundle_address": source_addresses[2],
                "resolution_address": "adapter-resolution:" + "0" * 64,
                "claim_collection_bundle_address": source_addresses[3],
                "claim_collection_address": "adapter-claim-collection:" + "0" * 64,
                "resolved_element_count": 0,
                "attribution_count": 0,
                "claim_count": 0,
                "source_bundle_addresses": list(source_addresses),
            }
        )

        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            with self.assertRaisesRegex(ValidationError, "hard item ceiling"):
                runtime._validate_persisted_adapter_closure(  # noqa: SLF001
                    manifest=manifest,
                    dossier=object(),  # type: ignore[arg-type]
                    event=event,
                    records=records,
                    remaining_claims=10_000,
                )
