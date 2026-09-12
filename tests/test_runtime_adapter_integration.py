from __future__ import annotations

import json
import tempfile
import threading
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
from urllib.request import Request, urlopen

from glio_noncode.adapters import (
    AdapterClaimCollectionReport,
    AdapterMetadata,
    AdapterRegistry,
    AdapterRegistrySnapshot,
    AdapterResolutionReport,
    RegistryEntry,
)
from glio_noncode.api import create_server
from glio_noncode.atlas import AtlasBundle, PublicAtlasRetriever
from glio_noncode.case_workflow import run_case
from glio_noncode.data_sources import EnrichmentResult, ReferenceBundle
from glio_noncode.errors import ValidationError
from glio_noncode.events import EventLog
from glio_noncode.hypotheses import HypothesisWorkLimits
from glio_noncode.models import (
    CandidateElement,
    CaseManifest,
    EdgeType,
    EvidenceClaim,
    EvidenceState,
    EvidenceTier,
    ReferenceContext,
    VariantIdentity,
)
from glio_noncode.runtime import CaseRuntime
from glio_noncode.serialization import canonical_bytes, content_hash
from glio_noncode.validation import ContractValidator

from .helpers import fixture_manifest
from .test_case_workflow import prepared as prepared_case_fixture


class RuntimeEvidenceAdapter:
    def __init__(
        self,
        element: CandidateElement,
        *,
        adapter_id: str = "runtime-evidence",
        invalid_edge: bool = False,
        claim_element_id: str | None = None,
        mutate_resolution_input: str | None = None,
        mutate_element_during_claims: bool = False,
    ) -> None:
        self.element = element
        self.invalid_edge = invalid_edge
        self.claim_element_id = claim_element_id
        self.mutate_resolution_input = mutate_resolution_input
        self.mutate_element_during_claims = mutate_element_during_claims
        self.metadata = AdapterMetadata(
            adapter_id=adapter_id,
            display_name="Runtime evidence fixture",
            version="2026.09",
            license="synthetic-fixture",
            data_access="local_fixture",
            supported_contexts=(element.context.key,),
            channels=("adapter_signal",),
            failure_modes=("empty_result",),
            validation_status="integration-tested",
            source_ids=(element.source_id,),
        )

    def resolve_variant_elements(
        self,
        variant: VariantIdentity,
        context: ReferenceContext,
    ) -> tuple[CandidateElement, ...]:
        if self.mutate_resolution_input == "context":
            object.__setattr__(context, "source_version", "mutated-by-adapter")
        if self.mutate_resolution_input == "variant":
            object.__setattr__(variant, "start", variant.start + 1)
        return (self.element,)

    def resolve_elements(
        self,
        variant_id: str,
        context: ReferenceContext,
    ) -> tuple[CandidateElement, ...]:
        raise AssertionError("typed variant resolution must take precedence")

    def collect_claims(
        self,
        variant_id: str,
        element_id: str,
        context: ReferenceContext,
    ) -> tuple[EvidenceClaim, ...]:
        if self.mutate_element_during_claims:
            object.__setattr__(self.element, "start", self.element.start + 7)
        edge_id = "edge-invalid"
        if not self.invalid_edge:
            target_element_id = self.claim_element_id or element_id
            digest = content_hash(
                {
                    "source": variant_id,
                    "target": target_element_id,
                    "type": EdgeType.VARIANT_TO_ELEMENT.value,
                }
            ).split(":", 1)[1]
            edge_id = f"edge-{digest[:20]}"
        return (
            EvidenceClaim(
                evidence_id=content_hash(
                    {
                        "adapter": self.metadata.adapter_id,
                        "variant": variant_id,
                        "element": element_id,
                    },
                    prefix="claim",
                ),
                edge_id=edge_id,
                source_id=self.element.source_id,
                channel="adapter_signal",
                state=EvidenceState.SUPPORTED,
                tier=EvidenceTier.EXPERIMENTAL,
                score=0.94,
                confidence=0.92,
                context=context,
                summary="Bounded external adapter support for this variant-element edge.",
                payload={"assay": "synthetic_runtime_fixture"},
                produced_by=self.metadata.adapter_id,
                created_at="2026-09-07T12:00:00+00:00",
            ),
        )


def _adapter_element(
    manifest: CaseManifest | None = None,
    *,
    conflicting: bool = False,
) -> CandidateElement:
    manifest = fixture_manifest() if manifest is None else manifest
    original = manifest.candidate_elements[0]
    return replace(
        original,
        element_id=(original.element_id if conflicting else "enhancer-adapter-runtime"),
        start=original.start + (1 if conflicting else 20),
        end=original.end + (1 if conflicting else 20),
        source_id="runtime-adapter-source",
        context=manifest.context,
        target_genes=("GENE_ADAPTER",),
        state_ids=("state-adapter-supported",),
        annotations={"mechanism": "adapter-backed regulatory activity"},
    )


class RuntimeAdapterIntegrationTests(unittest.TestCase):
    def test_runtime_uses_the_atomically_captured_adapter_entries(self) -> None:
        manifest = fixture_manifest()
        adapter = RuntimeEvidenceAdapter(_adapter_element(manifest))
        registry = AdapterRegistry()
        registry.register(adapter)

        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory, adapter_registry=registry)
            with (
                patch.object(
                    AdapterRegistry,
                    "resolve_manifest",
                    side_effect=AssertionError("runtime recaptured adapter resolution entries"),
                ),
                patch.object(
                    AdapterRegistry,
                    "collect_claims",
                    side_effect=AssertionError("runtime recaptured adapter claim entries"),
                ),
            ):
                dossier = runtime.evaluate(
                    manifest,
                    adapter_ids=(adapter.metadata.adapter_id,),
                )
            snapshot = runtime.load_run_snapshot(dossier.run_id)
            self.assertEqual(snapshot.dossier, dossier)
            self.assertTrue(
                any(
                    claim.produced_by == adapter.metadata.adapter_id
                    for claim in dossier.evidence
                )
            )

    def test_requested_adapters_are_bound_before_any_source_callback(self) -> None:
        manifest = fixture_manifest()
        registry = AdapterRegistry()
        adapter = RuntimeEvidenceAdapter(
            _adapter_element(manifest),
            adapter_id="late-runtime-adapter",
        )
        reference_calls: list[str] = []

        class RegisteringRetriever:
            def enrich_manifest(self, value: CaseManifest) -> EnrichmentResult:
                reference_calls.append(value.case_id)
                registry.register(adapter)
                raise AssertionError("unbound adapter registration callback ran")

        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(
                directory,
                reference_retriever=RegisteringRetriever(),
                adapter_registry=registry,
            )
            with self.assertRaisesRegex(
                ValidationError,
                "adapter is not registered: late-runtime-adapter",
            ):
                runtime.evaluate(
                    manifest,
                    live_reference=True,
                    adapter_ids=("late-runtime-adapter",),
                )
            self.assertEqual(reference_calls, [])
            self.assertEqual(registry.snapshot().adapters, ())
            self.assertEqual(tuple(runtime.store.store.objects.glob("*.json")), ())

    def test_selected_adapter_identity_is_restored_after_callback_substitution(self) -> None:
        manifest = fixture_manifest()

        class TrackingAdapter(RuntimeEvidenceAdapter):
            def __init__(
                self,
                element: CandidateElement,
                *,
                adapter_id: str = "runtime-evidence",
            ) -> None:
                super().__init__(element, adapter_id=adapter_id)
                self.resolve_calls = 0
                self.claim_calls = 0

            def resolve_variant_elements(
                self,
                variant: VariantIdentity,
                context: ReferenceContext,
            ) -> tuple[CandidateElement, ...]:
                self.resolve_calls += 1
                return super().resolve_variant_elements(variant, context)

            def collect_claims(
                self,
                variant_id: str,
                element_id: str,
                context: ReferenceContext,
            ) -> tuple[EvidenceClaim, ...]:
                self.claim_calls += 1
                return super().collect_claims(variant_id, element_id, context)

        original = TrackingAdapter(_adapter_element(manifest))
        substituted = TrackingAdapter(
            replace(
                _adapter_element(manifest),
                element_id="enhancer-substituted-runtime",
            )
        )
        self.assertEqual(original.metadata, substituted.metadata)
        unrelated = TrackingAdapter(
            _adapter_element(manifest),
            adapter_id="unrelated-runtime-adapter",
        )
        registry = AdapterRegistry()
        registry.register(original)
        reference_bundle = ReferenceBundle.create(
            variant_id=manifest.variants[0].variant_id,
            context=manifest.context,
            sequence=None,
            elements=(),
            raw_features=(),
            receipts=(),
            warnings=(),
        )

        class SubstitutingRetriever:
            def enrich_manifest(self, value: CaseManifest) -> EnrichmentResult:
                registry.register(unrelated)
                with registry._lock:  # noqa: SLF001 - adversarial registry mutation
                    registry._entries[original.metadata.adapter_id] = RegistryEntry(  # noqa: SLF001
                        substituted.metadata,
                        substituted,
                        substituted.metadata.content_address,
                    )
                return EnrichmentResult(value, (reference_bundle,), ())

        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(
                directory,
                reference_retriever=SubstitutingRetriever(),  # type: ignore[arg-type]
                adapter_registry=registry,
            )
            with self.assertRaisesRegex(
                ValidationError,
                "runtime evaluation configuration changed",
            ):
                runtime.evaluate(
                    manifest,
                    live_reference=True,
                    adapter_ids=(original.metadata.adapter_id,),
                )
            _snapshot, entries = registry.selected_entries((original.metadata.adapter_id,))
            self.assertIs(entries[0].adapter, original)
            self.assertEqual(
                tuple(item.adapter_id for item in registry.snapshot().adapters),
                (original.metadata.adapter_id, unrelated.metadata.adapter_id),
            )
            self.assertEqual(original.resolve_calls, 0)
            self.assertEqual(substituted.resolve_calls, 0)
            self.assertEqual(tuple(runtime.store.store.objects.glob("*.json")), ())
            self.assertEqual(tuple(runtime.store.runs.glob("*.json")), ())

            dossier = runtime.evaluate(
                manifest,
                adapter_ids=(original.metadata.adapter_id,),
            )
            self.assertEqual(dossier.case_id, manifest.case_id)
            self.assertEqual(original.resolve_calls, 1)
            self.assertEqual(original.claim_calls, 1)
            self.assertEqual(substituted.resolve_calls, 0)
            self.assertEqual(substituted.claim_calls, 0)

    def test_adapter_source_budget_stages_resolution_before_claim_callbacks(self) -> None:
        manifest = fixture_manifest()

        class TrackingAdapter(RuntimeEvidenceAdapter):
            def __init__(self, element: CandidateElement) -> None:
                super().__init__(element)
                self.calls: list[str] = []

            def resolve_variant_elements(
                self,
                variant: VariantIdentity,
                context: ReferenceContext,
            ) -> tuple[CandidateElement, ...]:
                self.calls.append("resolve")
                return super().resolve_variant_elements(variant, context)

            def collect_claims(
                self,
                variant_id: str,
                element_id: str,
                context: ReferenceContext,
            ) -> tuple[EvidenceClaim, ...]:
                self.calls.append("claims")
                return super().collect_claims(variant_id, element_id, context)

        adapter = TrackingAdapter(_adapter_element(manifest))
        registry = AdapterRegistry()
        registry.register(adapter)
        adapter_ids = ("runtime-evidence",)

        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(
                directory,
                adapter_registry=registry,
                source_closure_max_bytes=1,
            )
            with self.assertRaisesRegex(ValidationError, "aggregate canonical byte ceiling"):
                runtime.evaluate(manifest, adapter_ids=adapter_ids)
            self.assertEqual(adapter.calls, [])
            self.assertEqual(tuple(runtime.store.store.objects.glob("*.json")), ())

        snapshot = registry.selected_snapshot(adapter_ids)
        resolution = registry.resolve_manifest(manifest, adapter_ids)
        adapter.calls.clear()
        snapshot_budget = (
            len(canonical_bytes(manifest.to_dict()))
            + len(canonical_bytes(snapshot.to_dict()))
        )
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(
                directory,
                adapter_registry=registry,
                source_closure_max_bytes=snapshot_budget,
            )
            with self.assertRaisesRegex(ValidationError, "aggregate canonical byte ceiling"):
                runtime.evaluate(manifest, adapter_ids=adapter_ids)
            self.assertEqual(adapter.calls, [])
            self.assertEqual(tuple(runtime.store.store.objects.glob("*.json")), ())

        resolution_budget = (
            snapshot_budget
            + len(canonical_bytes(resolution.to_dict()))
        )
        adapter.calls.clear()
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(
                directory,
                adapter_registry=registry,
                source_closure_max_bytes=resolution_budget,
            )
            with self.assertRaisesRegex(ValidationError, "aggregate canonical byte ceiling"):
                runtime.evaluate(manifest, adapter_ids=adapter_ids)
            self.assertEqual(adapter.calls, ["resolve"])
            self.assertEqual(tuple(runtime.store.store.objects.glob("*.json")), ())

    def test_atlas_claims_reduce_adapter_allowance_before_claim_callback(self) -> None:
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
            def enrich_manifest(self, value: CaseManifest) -> EnrichmentResult:
                return EnrichmentResult(value, (reference_bundle,), ())

        class StubAtlas:
            def retrieve(
                self,
                variant: VariantIdentity,
                context: ReferenceContext,
            ) -> AtlasBundle:
                return PublicAtlasRetriever().retrieve(
                    variant,
                    context,
                    reference_bundle=reference_bundle,
                )

        class TrackingAdapter(RuntimeEvidenceAdapter):
            def __init__(self, element: CandidateElement) -> None:
                super().__init__(element)
                self.claim_calls = 0

            def collect_claims(
                self,
                variant_id: str,
                element_id: str,
                context: ReferenceContext,
            ) -> tuple[EvidenceClaim, ...]:
                self.claim_calls += 1
                return super().collect_claims(variant_id, element_id, context)

        adapter = TrackingAdapter(_adapter_element(manifest))
        registry = AdapterRegistry()
        registry.register(adapter)
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(
                directory,
                reference_retriever=StubRetriever(),  # type: ignore[arg-type]
                atlas_retriever=StubAtlas(),  # type: ignore[arg-type]
                adapter_registry=registry,
                hypothesis_limits=HypothesisWorkLimits(max_external_claims=2),
            )
            with self.assertRaisesRegex(ValidationError, "total claim ceiling"):
                runtime.evaluate(
                    manifest,
                    live_reference=True,
                    adapter_ids=("runtime-evidence",),
                )
            self.assertEqual(adapter.claim_calls, 0)
            self.assertEqual(tuple(runtime.store.store.objects.glob("*.json")), ())

    def test_native_per_edge_claim_exhaustion_stops_adapter_callback(self) -> None:
        manifest = fixture_manifest()

        class TrackingAdapter(RuntimeEvidenceAdapter):
            def __init__(self, element: CandidateElement) -> None:
                super().__init__(element)
                self.claim_calls = 0

            def collect_claims(
                self,
                variant_id: str,
                element_id: str,
                context: ReferenceContext,
            ) -> tuple[EvidenceClaim, ...]:
                self.claim_calls += 1
                return super().collect_claims(variant_id, element_id, context)

        adapter = TrackingAdapter(_adapter_element(manifest))
        registry = AdapterRegistry()
        registry.register(adapter)
        adapter_ids = (adapter.metadata.adapter_id,)
        resolution = registry.resolve_manifest(manifest, adapter_ids)

        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory, adapter_registry=registry)
            effective = replace(
                manifest,
                candidate_elements=runtime._merge_adapter_elements(  # noqa: SLF001
                    manifest,
                    resolution,
                ),
            )
            baseline = runtime.builder.build(effective, runtime._run_id(effective))  # noqa: SLF001
            target_edge = RuntimeEvidenceAdapter.collect_claims(
                adapter,
                manifest.variants[0].variant_id,
                resolution.items[0].element.element_id,
                manifest.context,
            )[0].edge_id
            claims_by_edge: dict[str, int] = {}
            for claim in baseline.claims:
                claims_by_edge[claim.edge_id] = claims_by_edge.get(claim.edge_id, 0) + 1
            target_count = claims_by_edge[target_edge]
            self.assertEqual(target_count, max(claims_by_edge.values()))
            runtime.validator = ContractValidator(
                limits=replace(
                    runtime.validator.limits,
                    max_claims_per_edge=target_count,
                )
            )

            with self.assertRaisesRegex(ValidationError, "per-edge claim ceiling"):
                runtime.evaluate(manifest, adapter_ids=adapter_ids)
            self.assertEqual(adapter.claim_calls, 0)
            self.assertEqual(tuple(runtime.store.store.objects.glob("*.json")), ())
            self.assertEqual(tuple(runtime.store.runs.glob("*.json")), ())

    def test_noop_live_reference_and_adapter_share_one_replayable_base_record(self) -> None:
        manifest = fixture_manifest()

        class StubRetriever:
            def enrich_manifest(self, value: CaseManifest) -> EnrichmentResult:
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

        registry = AdapterRegistry()
        registry.register(RuntimeEvidenceAdapter(_adapter_element(manifest)))
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(
                directory,
                reference_retriever=StubRetriever(),  # type: ignore[arg-type]
                adapter_registry=registry,
            )
            dossier = runtime.evaluate(
                manifest,
                live_reference=True,
                adapter_ids=("runtime-evidence",),
            )
            snapshot = runtime.load_run_snapshot(dossier.run_id)
            self.assertEqual(snapshot.dossier, dossier)
            self.assertEqual(dossier.source_bundle_addresses[0], manifest.content_address)
            self.assertEqual(len(dossier.source_bundle_addresses), 5)

    def test_replay_applies_configured_external_claim_limit_to_adapter_reports(self) -> None:
        manifest = fixture_manifest()

        class TwoClaimAdapter(RuntimeEvidenceAdapter):
            def collect_claims(
                self,
                variant_id: str,
                element_id: str,
                context: ReferenceContext,
            ) -> tuple[EvidenceClaim, ...]:
                first = super().collect_claims(variant_id, element_id, context)[0]
                second = replace(
                    first,
                    evidence_id=content_hash(
                        {
                            "adapter": self.metadata.adapter_id,
                            "variant": variant_id,
                            "element": element_id,
                            "replicate": 2,
                        },
                        prefix="claim",
                    ),
                    payload={"assay": "synthetic_runtime_fixture", "replicate": 2},
                )
                return first, second

        registry = AdapterRegistry()
        registry.register(TwoClaimAdapter(_adapter_element(manifest)))
        with tempfile.TemporaryDirectory() as directory:
            writer = CaseRuntime(directory, adapter_registry=registry)
            dossier = writer.evaluate(manifest, adapter_ids=("runtime-evidence",))
            reader = CaseRuntime(
                directory,
                hypothesis_limits=HypothesisWorkLimits(max_external_claims=1),
            )
            with self.assertRaisesRegex(ValidationError, "external_claims.*maximum of 1"):
                reader.load_run_snapshot(dossier.run_id)

    def test_adapter_id_cannot_collide_with_native_evidence_producer(self) -> None:
        manifest = fixture_manifest()
        registry = AdapterRegistry()
        registry.register(
            RuntimeEvidenceAdapter(
                _adapter_element(manifest),
                adapter_id="deterministic_runtime",
            )
        )
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory, adapter_registry=registry)
            with self.assertRaisesRegex(ValidationError, "reserved evidence producers"):
                runtime.evaluate(manifest, adapter_ids=("deterministic_runtime",))
            self.assertEqual(tuple(runtime.store.store.objects.glob("*.json")), ())
            self.assertEqual(tuple(runtime.store.runs.glob("*.json")), ())

    def test_live_reference_and_adapter_events_bind_each_manifest_stage(self) -> None:
        manifest = fixture_manifest()
        reference_element = replace(
            manifest.candidate_elements[0],
            element_id="element-reference-stage",
            start=manifest.candidate_elements[0].start + 10,
            end=manifest.candidate_elements[0].end + 10,
        )
        reference_manifest = replace(
            manifest,
            candidate_elements=manifest.candidate_elements + (reference_element,),
            input_versions={**manifest.input_versions, "live_stub": "2026.09"},
        )

        class StubRetriever:
            def enrich_manifest(self, value: CaseManifest) -> EnrichmentResult:
                bundle = ReferenceBundle.create(
                    variant_id=value.variants[0].variant_id,
                    context=value.context,
                    sequence=None,
                    elements=(reference_element,),
                    raw_features=(),
                    receipts=(),
                    warnings=(),
                )
                return EnrichmentResult(reference_manifest, (bundle,), ())

        registry = AdapterRegistry()
        registry.register(RuntimeEvidenceAdapter(_adapter_element(reference_manifest)))
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(
                directory,
                reference_retriever=StubRetriever(),  # type: ignore[arg-type]
                adapter_registry=registry,
            )
            dossier = runtime.evaluate(
                manifest,
                live_reference=True,
                adapter_ids=("runtime-evidence",),
            )
            snapshot = runtime.load_run_snapshot(dossier.run_id)
            events = snapshot.event_log.all()
            self.assertEqual(
                tuple(event.event_type for event in events[:6]),
                (
                    "case_received",
                    "public_reference_enriched",
                    "adapter_evidence_collected",
                    "hypotheses_built",
                    "validation_routes_planned",
                    "dossier_created",
                ),
            )
            reference_event = events[1]
            adapter_event = events[2]
            self.assertEqual(
                reference_event.payload["submitted_input_address"],
                manifest.content_address,
            )
            self.assertEqual(
                reference_event.payload["effective_input_address"],
                reference_manifest.content_address,
            )
            self.assertEqual(
                adapter_event.payload["base_input_address"],
                reference_manifest.content_address,
            )
            self.assertEqual(
                adapter_event.payload["effective_input_address"],
                dossier.input_address,
            )
            self.assertEqual(
                dossier.source_bundle_addresses[2:],
                tuple(adapter_event.payload["source_bundle_addresses"]),
            )

    def test_resolution_callback_inputs_are_detached_and_mutation_fails_before_writes(
        self,
    ) -> None:
        for target in ("context", "variant"):
            with self.subTest(target=target):
                manifest = fixture_manifest()
                original = manifest.to_dict()
                registry = AdapterRegistry()
                registry.register(
                    RuntimeEvidenceAdapter(
                        _adapter_element(manifest),
                        mutate_resolution_input=target,
                    )
                )
                with tempfile.TemporaryDirectory() as directory:
                    runtime = CaseRuntime(directory, adapter_registry=registry)
                    with self.assertRaisesRegex(
                        ValidationError,
                        "mutated its resolution invocation inputs",
                    ):
                        runtime.evaluate(manifest, adapter_ids=("runtime-evidence",))
                    self.assertEqual(manifest.to_dict(), original)
                    self.assertEqual(tuple(runtime.store.store.objects.glob("*.json")), ())
                    self.assertEqual(tuple(runtime.store.runs.glob("*.json")), ())

    def test_adapter_private_element_mutation_cannot_poison_canonical_run(self) -> None:
        manifest = fixture_manifest()
        element = _adapter_element(manifest)
        expected_start = element.start
        registry = AdapterRegistry()
        registry.register(
            RuntimeEvidenceAdapter(
                element,
                mutate_element_during_claims=True,
            )
        )
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory, adapter_registry=registry)
            dossier = runtime.evaluate(manifest, adapter_ids=("runtime-evidence",))
            snapshot = runtime.load_run_snapshot(dossier.run_id)
            persisted = next(
                item
                for item in snapshot.manifest.candidate_elements
                if item.element_id == element.element_id
            )
            self.assertEqual(persisted.start, expected_start)
            self.assertEqual(snapshot.replay.run_id, dossier.run_id)
            self.assertTrue(snapshot.replay.event_chain_valid)
            self.assertEqual(element.start, expected_start + 7)

    def test_reserved_adapter_manifest_versions_fail_before_persistence(self) -> None:
        manifest = fixture_manifest()
        poisoned = replace(
            manifest,
            input_versions={
                **manifest.input_versions,
                "adapter_registry_snapshot": "sha256:" + "0" * 64,
            },
        )
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            with self.assertRaisesRegex(ValidationError, "runtime-reserved adapter"):
                runtime.evaluate(poisoned)
            self.assertEqual(tuple(runtime.store.store.objects.glob("*.json")), ())
            self.assertEqual(tuple(runtime.store.runs.glob("*.json")), ())

    def test_adapter_claim_cannot_escape_its_resolution_item(self) -> None:
        manifest = fixture_manifest()
        existing_element = manifest.candidate_elements[0]
        registry = AdapterRegistry()
        registry.register(
            RuntimeEvidenceAdapter(
                _adapter_element(manifest),
                claim_element_id=existing_element.element_id,
            )
        )
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory, adapter_registry=registry)
            with self.assertRaisesRegex(ValidationError, "attributed resolution item"):
                runtime.evaluate(manifest, adapter_ids=("runtime-evidence",))
            self.assertEqual(tuple(runtime.store.store.objects.glob("*.json")), ())
            self.assertEqual(tuple(runtime.store.runs.glob("*.json")), ())

    def test_rechained_adapter_event_after_dossier_is_rejected(self) -> None:
        manifest = fixture_manifest()
        registry = AdapterRegistry()
        registry.register(RuntimeEvidenceAdapter(_adapter_element(manifest)))
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory, adapter_registry=registry)
            dossier = runtime.evaluate(manifest, adapter_ids=("runtime-evidence",))
            snapshot = runtime.load_run_snapshot(dossier.run_id)
            events = snapshot.event_log.all()
            self.assertEqual(events[1].event_type, "adapter_evidence_collected")
            reordered = EventLog(dossier.run_id)
            for event in (events[0], *events[2:], events[1]):
                reordered.append(
                    event.event_type,
                    event.payload,
                    event_id=event.event_id,
                )
            self.assertTrue(reordered.verify())
            with self.assertRaisesRegex(ValidationError, "canonically ordered"):
                runtime._validate_persisted_source_closure(  # noqa: SLF001
                    manifest=snapshot.manifest,
                    dossier=snapshot.dossier,
                    events=reordered.all(),
                    rna_address=None,
                )

    def test_adapter_claims_materialize_into_replay_closed_hypotheses(self) -> None:
        manifest = fixture_manifest()
        registry = AdapterRegistry()
        registry.register(RuntimeEvidenceAdapter(_adapter_element()))

        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory, adapter_registry=registry)
            dossier = runtime.evaluate(manifest, adapter_ids=("runtime-evidence",))
            snapshot = runtime.load_run_snapshot(dossier.run_id)
            events = snapshot.event_log.all()
            adapter_event = next(
                event for event in events if event.event_type == "adapter_evidence_collected"
            )
            source_addresses = adapter_event.payload["source_bundle_addresses"]
            self.assertEqual(len(source_addresses), 4)

            source_records = tuple(
                runtime.store.store.get(address) for address in source_addresses
            )
            base, registry_raw, resolution_raw, claims_raw = source_records
            self.assertEqual(content_hash(base), source_addresses[0])
            self.assertEqual(
                AdapterRegistrySnapshot.from_dict(registry_raw),
                registry.snapshot(),
            )
            resolution = AdapterResolutionReport.from_dict(resolution_raw)
            report = AdapterClaimCollectionReport.from_dict(claims_raw)
            self.assertEqual(report.resolution_address, resolution.content_address)
            self.assertEqual(report.claim_count, 1)
            self.assertIn(_adapter_element(), snapshot.manifest.candidate_elements)
            for key, address in zip(
                (
                    "adapter_input_manifest",
                    "adapter_registry_snapshot",
                    "adapter_resolution_report",
                    "adapter_claim_collection_report",
                ),
                source_addresses,
                strict=True,
            ):
                self.assertEqual(snapshot.manifest.input_versions[key], address)

            claim = report.claims[0]
            persisted = next(
                item for item in dossier.evidence if item.evidence_id == claim.evidence_id
            )
            self.assertEqual(persisted, claim)
            matching_edges = tuple(
                edge
                for hypothesis in dossier.hypotheses
                for edge in hypothesis.edges
                if claim.evidence_id in edge.claim_ids
            )
            self.assertGreater(len(matching_edges), 0)
            self.assertTrue(all(edge.edge_id == claim.edge_id for edge in matching_edges))

        with tempfile.TemporaryDirectory() as baseline_directory:
            baseline = CaseRuntime(baseline_directory).evaluate(manifest)
            self.assertNotEqual(baseline.run_id, dossier.run_id)
            self.assertNotEqual(baseline.content_address, dossier.content_address)

    def test_adapter_failures_and_element_conflicts_write_no_run_objects(self) -> None:
        cases: tuple[tuple[RuntimeEvidenceAdapter, str], ...] = (
            (
                RuntimeEvidenceAdapter(_adapter_element(), invalid_edge=True),
                "attributed resolution item",
            ),
            (
                RuntimeEvidenceAdapter(_adapter_element(conflicting=True)),
                "conflicts with an existing manifest element",
            ),
        )
        for adapter, expected in cases:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as directory:
                registry = AdapterRegistry()
                registry.register(adapter)
                runtime = CaseRuntime(directory, adapter_registry=registry)
                with self.assertRaisesRegex(ValidationError, expected):
                    runtime.evaluate(
                        fixture_manifest(),
                        adapter_ids=(adapter.metadata.adapter_id,),
                    )
                self.assertEqual(tuple(runtime.store.store.objects.glob("*.json")), ())
                self.assertEqual(tuple(runtime.store.runs.glob("*.json")), ())

    def test_adapter_selection_is_exact_and_requires_a_configured_registry(self) -> None:
        manifest = fixture_manifest()
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            for malformed in (["runtime-evidence"], (1,), "runtime-evidence"):
                with self.subTest(malformed=malformed), self.assertRaises(ValidationError):
                    runtime.evaluate(manifest, adapter_ids=malformed)  # type: ignore[arg-type]
            with self.assertRaisesRegex(ValidationError, "configured AdapterRegistry"):
                runtime.evaluate(manifest, adapter_ids=("runtime-evidence",))
            self.assertEqual(tuple(runtime.store.store.objects.glob("*.json")), ())

    def test_case_workflow_exposes_adapter_selection_and_dynamic_identity(self) -> None:
        prepared = prepared_case_fixture()
        assert prepared.manifest is not None
        registry = AdapterRegistry()
        registry.register(RuntimeEvidenceAdapter(_adapter_element(prepared.manifest)))

        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory, adapter_registry=registry)
            result = run_case(
                prepared,
                runtime=runtime,
                adapter_ids=("runtime-evidence",),
            )
            self.assertTrue(result.accepted, result.to_dict())
            assert result.dossier is not None
            self.assertNotEqual(result.dossier.run_id, prepared.run_id)
            runtime_receipt = result.stage_receipts[-1]
            self.assertEqual(runtime_receipt.metadata["adapter_ids"], ["runtime-evidence"])
            self.assertEqual(
                runtime_receipt.metadata["evaluation_run_id"],
                result.dossier.run_id,
            )
            snapshot = runtime.load_run_snapshot(result.dossier.run_id)
            self.assertIn(
                "adapter_claim_collection_report",
                snapshot.manifest.input_versions,
            )

        invalid = run_case(
            prepared,
            adapter_ids=("not canonical adapter id",),
        )
        self.assertFalse(invalid.accepted)
        self.assertIn("invalid_adapter_selection", {item.code for item in invalid.issues})

    def test_http_surface_lists_and_executes_configured_adapters(self) -> None:
        prepared = prepared_case_fixture()
        assert prepared.manifest is not None
        registry = AdapterRegistry()
        registry.register(RuntimeEvidenceAdapter(_adapter_element(prepared.manifest)))

        with tempfile.TemporaryDirectory() as directory:
            server = create_server(
                "127.0.0.1",
                0,
                Path(directory) / "data",
                adapter_registry=registry,
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                with urlopen(f"{base}/v1/case-workflow/adapters", timeout=5) as response:
                    advertised = json.loads(response.read().decode("utf-8"))
                self.assertTrue(advertised["configured"])
                self.assertEqual(advertised["adapter_ids"], ["runtime-evidence"])
                self.assertEqual(advertised["registry_snapshot"]["count"], 1)
                self.assertEqual(
                    advertised["adapter_metadata"],
                    [registry.list_metadata()[0].to_dict()],
                )

                request = Request(
                    f"{base}/v1/case-workflow/run",
                    data=json.dumps(
                        {
                            "prepared": prepared.to_dict(),
                            "adapter_ids": ["runtime-evidence"],
                        }
                    ).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urlopen(request, timeout=10) as response:
                    result = json.loads(response.read().decode("utf-8"))
                self.assertTrue(result["accepted"])
                self.assertNotEqual(result["dossier"]["run_id"], prepared.run_id)
                self.assertEqual(
                    result["stage_receipts"][-1]["metadata"]["adapter_ids"],
                    ["runtime-evidence"],
                )
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
