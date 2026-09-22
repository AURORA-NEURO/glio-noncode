"""Adversarial coverage for the executable adapter boundary."""

from __future__ import annotations

import copy
import unittest
from collections.abc import Iterator, Mapping
from dataclasses import replace
from threading import Event, Thread
from typing import Any

import glio_noncode.adapters as adapters_module
from glio_noncode.adapters import (
    ADAPTER_HARD_MAX_REGISTERED,
    AdapterLimits,
    AdapterMetadata,
    AdapterRegistry,
    AdapterRegistrySnapshot,
    AdapterRegistrySnapshotEntry,
    AdapterResolutionItem,
    AdapterResolutionReport,
    RegistryEntry,
    StaticElementAdapter,
)
from glio_noncode.errors import ValidationError
from glio_noncode.models import (
    CandidateElement,
    EvidenceClaim,
    EvidenceState,
    EvidenceTier,
    ReferenceContext,
    VariantIdentity,
)
from glio_noncode.serialization import canonical_bytes, content_hash

from .helpers import fixture_manifest


def _metadata(
    adapter_id: str = "fixture-adapter",
    *,
    source_ids: tuple[str, ...] = ("fixture-atlas-001",),
) -> AdapterMetadata:
    case = fixture_manifest()
    return AdapterMetadata(
        adapter_id=adapter_id,
        display_name=f"Fixture {adapter_id}",
        version="2026.08",
        license="synthetic-fixture",
        data_access="local_fixture",
        supported_contexts=(case.context.key,),
        channels=("regulatory_element",),
        failure_modes=("missing_context", "empty_result"),
        validation_status="tested",
        documentation_url="docs/OPERATIONS.md",
        source_ids=source_ids,
    )


def _claim(
    label: str,
    *,
    adapter_id: str,
    edge_id: str | None = None,
) -> EvidenceClaim:
    case = fixture_manifest()
    element = case.candidate_elements[0]
    gene_id = element.target_genes[0] if element.target_genes else element.element_id
    state_id = element.state_ids[0] if element.state_ids else "unresolved_state"
    shared_edge_digest = content_hash(
        {"source": gene_id, "target": state_id, "type": "gene_to_state"}
    ).split(":", 1)[1]
    return EvidenceClaim(
        evidence_id=content_hash({"adapter-claim": label}, prefix="claim"),
        edge_id=edge_id or f"edge-{shared_edge_digest[:20]}",
        source_id="fixture-atlas-001",
        channel="regulatory_element",
        state=EvidenceState.SUPPORTED,
        tier=EvidenceTier.REFERENCE,
        score=0.8,
        confidence=0.9,
        context=case.context,
        summary=f"Adapter claim {label}.",
        payload={"label": label},
        produced_by=adapter_id,
        created_at="2026-09-08T12:00:00+00:00",
    )


class _VariantAdapter:
    def __init__(
        self,
        metadata: AdapterMetadata,
        result: Any,
        *,
        drift_during_call: bool = False,
        claim_results: dict[str, tuple[EvidenceClaim, ...]] | None = None,
    ) -> None:
        self.metadata = metadata
        self.result = result
        self.drift_during_call = drift_during_call
        self.claim_results = {} if claim_results is None else claim_results
        self.seen: list[VariantIdentity] = []
        self.claim_seen: list[tuple[str, str]] = []

    def resolve_variant_elements(
        self,
        variant: VariantIdentity,
        context: ReferenceContext,
    ) -> Any:
        self.seen.append(variant)
        if self.drift_during_call:
            self.metadata = replace(self.metadata, version="2026.09", content_address="")
        return self.result

    def resolve_elements(
        self,
        variant_id: str,
        context: ReferenceContext,
    ) -> tuple[CandidateElement, ...]:
        raise AssertionError("the typed variant path must take precedence")

    def collect_claims(
        self,
        variant_id: str,
        element_id: str,
        context: ReferenceContext,
    ) -> tuple[Any, ...]:
        self.claim_seen.append((variant_id, element_id))
        return self.claim_results.get(element_id, ())


class _LegacyAdapter:
    def __init__(
        self,
        metadata: AdapterMetadata,
        elements: tuple[CandidateElement, ...],
    ) -> None:
        self.metadata = metadata
        self.elements = elements
        self.variant_ids: list[str] = []

    def resolve_elements(
        self,
        variant_id: str,
        context: ReferenceContext,
    ) -> tuple[CandidateElement, ...]:
        self.variant_ids.append(variant_id)
        return self.elements

    def collect_claims(
        self,
        variant_id: str,
        element_id: str,
        context: ReferenceContext,
    ) -> tuple[Any, ...]:
        return ()


class AdapterHardeningTests(unittest.TestCase):
    def test_limits_are_exact_and_downward_only(self) -> None:
        for overrides in (
            {"max_registered_adapters": True},
            {"max_registered_adapters": ADAPTER_HARD_MAX_REGISTERED + 1},
            {"max_selected_adapters": 65},
            {"max_elements_per_variant": 0},
            {"max_report_bytes": 0},
        ):
            with self.subTest(overrides=overrides), self.assertRaises(ValidationError):
                AdapterLimits(**overrides)

    def test_public_ceiling_rebinding_and_limit_mutation_cannot_expand_work(
        self,
    ) -> None:
        original = adapters_module.ADAPTER_HARD_MAX_REGISTERED
        try:
            adapters_module.ADAPTER_HARD_MAX_REGISTERED = 10**9
            with self.assertRaises(ValidationError):
                AdapterLimits(max_registered_adapters=original + 1)
        finally:
            adapters_module.ADAPTER_HARD_MAX_REGISTERED = original

        supplied = AdapterLimits(max_registered_adapters=1)
        registry = AdapterRegistry(supplied)
        object.__setattr__(supplied, "max_registered_adapters", 2)
        self.assertEqual(registry.limits.max_registered_adapters, 1)

        object.__setattr__(registry._limits, "max_registered_adapters", 2)
        with self.assertRaisesRegex(ValidationError, "limits were mutated"):
            registry.snapshot()

    def test_metadata_is_canonical_addressed_and_strictly_reopened(self) -> None:
        metadata = _metadata()
        self.assertEqual(
            metadata.content_address,
            content_hash(metadata.body(), prefix="adapter-metadata"),
        )
        self.assertEqual(metadata.failure_modes, ("empty_result", "missing_context"))
        self.assertEqual(AdapterMetadata.from_dict(metadata.to_dict()), metadata)

        tampered = copy.deepcopy(metadata.to_dict())
        tampered["version"] = "2026.09"
        with self.assertRaisesRegex(ValidationError, "content address"):
            AdapterMetadata.from_dict(tampered)
        unknown = copy.deepcopy(metadata.to_dict())
        unknown["extra"] = True
        with self.assertRaisesRegex(ValidationError, "fields are not exact"):
            AdapterMetadata.from_dict(unknown)

    def test_metadata_rejects_unsafe_or_ambiguous_declarations(self) -> None:
        invalid = (
            {"channels": ("regulatory_element", "regulatory_element")},
            {"failure_modes": ("",)},
            {"validation_status": "probably-good"},
            {"documentation_url": "http://example.test/docs"},
            {"documentation_url": "https://user:secret@example.test/docs"},
            {"documentation_url": "../OPERATIONS.md"},
            {"source_ids": ("unsafe source",)},
        )
        baseline = _metadata()
        for changes in invalid:
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                replace(baseline, content_address="", **changes)

    def test_snapshot_is_sorted_addressed_and_detached(self) -> None:
        case = fixture_manifest()
        registry = AdapterRegistry()
        registered: list[AdapterMetadata] = []

        def register(adapter_id: str) -> None:
            metadata = _metadata(adapter_id)
            registered.append(metadata)
            registry.register(StaticElementAdapter(metadata, case.candidate_elements))

        threads = [Thread(target=register, args=(item,)) for item in ("z", "a", "m")]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        snapshot = registry.snapshot()
        self.assertEqual(
            tuple(item.adapter_id for item in snapshot.adapters),
            ("a", "m", "z"),
        )
        self.assertEqual(registry.health(), snapshot.to_dict())
        self.assertEqual(
            snapshot.content_address,
            content_hash(snapshot.body(), prefix="adapter-registry"),
        )
        self.assertEqual(
            AdapterRegistrySnapshot.from_dict(snapshot.to_dict()),
            snapshot,
        )
        self.assertEqual(
            AdapterRegistrySnapshotEntry.from_dict(snapshot.adapters[0].to_dict()),
            snapshot.adapters[0],
        )
        forged_count = copy.deepcopy(snapshot.to_dict())
        forged_count["count"] += 1
        with self.assertRaisesRegex(ValidationError, "count is not derived"):
            AdapterRegistrySnapshot.from_dict(forged_count)
        unknown_entry = copy.deepcopy(snapshot.to_dict())
        unknown_entry["adapters"][0]["unknown"] = True
        with self.assertRaisesRegex(ValidationError, "fields are not exact"):
            AdapterRegistrySnapshot.from_dict(unknown_entry)
        with self.assertRaisesRegex(ValidationError, "hard entry ceiling"):
            AdapterRegistrySnapshot((snapshot.adapters[0],) * 257)
        listed = registry.list_metadata()
        self.assertTrue(all(item is not original for item in listed for original in registered))
        discovered_snapshot, discovered_metadata, discovered_limits = registry.discovery()
        self.assertEqual(discovered_snapshot, snapshot)
        self.assertEqual(
            tuple(item.adapter_id for item in discovered_metadata),
            tuple(item.adapter_id for item in discovered_snapshot.adapters),
        )
        self.assertEqual(discovered_limits, registry.limits)

    def test_returned_registry_entry_cannot_mutate_the_stored_metadata(self) -> None:
        case = fixture_manifest()
        registry = AdapterRegistry()
        entry = registry.register(StaticElementAdapter(_metadata(), case.candidate_elements))
        object.__setattr__(entry.metadata, "source_ids", ("forged-source",))

        snapshot = registry.snapshot()
        self.assertEqual(snapshot.adapters[0].source_ids, ("fixture-atlas-001",))

        stored = registry._entries[entry.metadata.adapter_id]  # noqa: SLF001
        object.__setattr__(stored.metadata, "source_ids", ("forged-source",))
        with self.assertRaisesRegex(ValidationError, "metadata snapshot drift"):
            registry.snapshot()

    def test_selected_entries_atomically_expose_exact_adapter_identities(self) -> None:
        case = fixture_manifest()
        first = _VariantAdapter(_metadata("a-first"), case.candidate_elements)
        second = _VariantAdapter(_metadata("z-second"), case.candidate_elements)
        registry = AdapterRegistry()
        registry.register(second)
        registry.register(first)

        snapshot, entries = registry.selected_entries(("z-second", "a-first"))

        self.assertEqual(
            tuple(item.adapter_id for item in snapshot.adapters),
            ("a-first", "z-second"),
        )
        self.assertIs(entries[0].adapter, first)
        self.assertIs(entries[1].adapter, second)
        object.__setattr__(entries[0].metadata, "source_ids", ("forged-source",))
        self.assertEqual(
            registry.selected_entries(("a-first", "z-second"))[1][0].metadata.source_ids,
            ("fixture-atlas-001",),
        )

    def test_captured_execution_pins_identities_across_registry_substitution(self) -> None:
        case = fixture_manifest()
        metadata = _metadata("pinned-adapter")
        original = _VariantAdapter(metadata, case.candidate_elements)
        substitute = _VariantAdapter(metadata, case.candidate_elements)
        registry = AdapterRegistry()
        registry.register(original)
        snapshot, entries = registry.selected_entries((metadata.adapter_id,))

        release_substitution = Event()
        substitution_complete = Event()
        substitution_errors: list[BaseException] = []

        def substitute_registry_slot() -> None:
            try:
                if not release_substitution.wait(timeout=2):
                    raise AssertionError("capture-to-substitution synchronization timed out")
                replacement = RegistryEntry(metadata, substitute, metadata.content_address)
                with registry._lock:  # noqa: SLF001 - synchronized adversarial mutation
                    registry._entries[metadata.adapter_id] = replacement  # noqa: SLF001
            except BaseException as exc:  # noqa: BLE001 - propagate worker failures
                substitution_errors.append(exc)
            finally:
                substitution_complete.set()

        worker = Thread(target=substitute_registry_slot)
        worker.start()
        release_substitution.set()
        self.assertTrue(substitution_complete.wait(timeout=2))
        worker.join(timeout=2)
        self.assertFalse(worker.is_alive())
        self.assertEqual(substitution_errors, [])

        resolution = registry.resolve_manifest_entries(case, snapshot, entries)
        report = registry.collect_claims_entries(
            case,
            resolution,
            snapshot,
            entries,
        )

        self.assertEqual(len(original.seen), 1)
        self.assertEqual(len(original.claim_seen), len(resolution.items))
        self.assertEqual(substitute.seen, [])
        self.assertEqual(substitute.claim_seen, [])
        self.assertEqual(report.registry_snapshot, snapshot)

        # The synchronized mutation really did replace the live slot; only an
        # ordinary recapturing call observes and executes the substitute.
        registry.resolve_manifest(case, (metadata.adapter_id,))
        self.assertEqual(len(substitute.seen), 1)

    def test_captured_execution_rejects_non_exact_or_incongruent_capabilities(self) -> None:
        case = fixture_manifest()
        first = _VariantAdapter(_metadata("a-first"), case.candidate_elements)
        second = _VariantAdapter(_metadata("z-second"), case.candidate_elements)
        registry = AdapterRegistry()
        registry.register(first)
        registry.register(second)
        snapshot, entries = registry.selected_entries(("z-second", "a-first"))

        with self.assertRaisesRegex(ValidationError, "exact AdapterRegistrySnapshot"):
            registry.resolve_manifest_entries(
                case,
                object(),  # type: ignore[arg-type]
                entries,
            )
        with self.assertRaisesRegex(ValidationError, "exact tuple"):
            registry.resolve_manifest_entries(
                case,
                snapshot,
                list(entries),  # type: ignore[arg-type]
            )
        with self.assertRaisesRegex(ValidationError, "exact RegistryEntry"):
            registry.resolve_manifest_entries(
                case,
                snapshot,
                (entries[0], object()),  # type: ignore[arg-type]
            )
        with self.assertRaisesRegex(ValidationError, "sorted and unique"):
            registry.resolve_manifest_entries(case, snapshot, tuple(reversed(entries)))

        first_snapshot, _ = registry.selected_entries(("a-first",))
        with self.assertRaisesRegex(ValidationError, "exactly cover"):
            registry.resolve_manifest_entries(case, first_snapshot, entries)

        foreign = _VariantAdapter(
            _metadata("a-first", source_ids=("foreign-source",)),
            case.candidate_elements,
        )
        incongruent = RegistryEntry(
            entries[0].metadata,
            foreign,
            entries[0].metadata_address,
        )
        with self.assertRaisesRegex(ValidationError, "metadata drift"):
            registry.resolve_manifest_entries(
                case,
                snapshot,
                (incongruent, entries[1]),
            )

    def test_registration_rolls_back_when_prospective_snapshot_is_one_byte_too_large(
        self,
    ) -> None:
        case = fixture_manifest()
        first_metadata = _metadata("a-first")
        second_metadata = _metadata("z-second")
        probe = AdapterRegistry()
        probe.register(_VariantAdapter(first_metadata, ()))
        probe.register(_VariantAdapter(second_metadata, ()))
        two_entry_size = len(canonical_bytes(probe.snapshot().to_dict()))

        registry = AdapterRegistry(AdapterLimits(max_report_bytes=two_entry_size - 1))
        registry.register(_VariantAdapter(first_metadata, case.candidate_elements))
        with self.assertRaisesRegex(ValidationError, "registry snapshot.*byte ceiling"):
            registry.register(_VariantAdapter(second_metadata, case.candidate_elements))

        self.assertEqual(registry.snapshot().count, 1)
        with self.assertRaisesRegex(ValidationError, "not registered"):
            registry.get(second_metadata.adapter_id)

    def test_registration_is_not_visible_until_metadata_stability_succeeds(self) -> None:
        stable_metadata = _metadata("blocking-drift")
        stability_started = Event()
        release_stability = Event()

        class BlockingDriftAdapter:
            def __init__(self) -> None:
                self.metadata_reads = 0

            @property
            def metadata(self) -> AdapterMetadata:
                self.metadata_reads += 1
                if self.metadata_reads == 2:
                    stability_started.set()
                    release_stability.wait(timeout=5)
                    return replace(
                        stable_metadata,
                        version="2026.09",
                        content_address="",
                    )
                return stable_metadata

            def resolve_elements(
                self,
                variant_id: str,
                context: ReferenceContext,
            ) -> tuple[CandidateElement, ...]:
                return ()

            def collect_claims(
                self,
                variant_id: str,
                element_id: str,
                context: ReferenceContext,
            ) -> tuple[EvidenceClaim, ...]:
                return ()

        registry = AdapterRegistry()
        adapter = BlockingDriftAdapter()
        registration_errors: list[Exception] = []
        observed_snapshots: list[AdapterRegistrySnapshot] = []
        snapshot_errors: list[Exception] = []
        snapshot_started = Event()
        snapshot_done = Event()

        def register() -> None:
            try:
                registry.register(adapter)
            except Exception as exc:
                registration_errors.append(exc)

        def snapshot() -> None:
            snapshot_started.set()
            try:
                observed_snapshots.append(registry.snapshot())
            except Exception as exc:
                snapshot_errors.append(exc)
            finally:
                snapshot_done.set()

        registration_thread = Thread(target=register)
        snapshot_thread = Thread(target=snapshot)
        registration_thread.start()
        try:
            self.assertTrue(stability_started.wait(timeout=2))
            snapshot_thread.start()
            self.assertTrue(snapshot_started.wait(timeout=2))
            self.assertFalse(snapshot_done.wait(timeout=0.05))
        finally:
            release_stability.set()
            registration_thread.join(timeout=2)
            if snapshot_thread.ident is not None:
                snapshot_thread.join(timeout=2)

        self.assertFalse(registration_thread.is_alive())
        self.assertFalse(snapshot_thread.is_alive())
        self.assertEqual(len(registration_errors), 1)
        self.assertIsInstance(registration_errors[0], ValidationError)
        self.assertEqual(snapshot_errors, [])
        self.assertEqual(tuple(snapshot.count for snapshot in observed_snapshots), (0,))
        self.assertEqual(registry.snapshot().count, 0)

    def test_registration_candidate_is_absent_from_reentrant_stability_snapshot(
        self,
    ) -> None:
        stable_metadata = _metadata("reentrant-registration")
        registry = AdapterRegistry()

        class ReentrantMetadataAdapter:
            def __init__(self) -> None:
                self.metadata_reads = 0
                self.observed_counts: list[int] = []

            @property
            def metadata(self) -> AdapterMetadata:
                self.metadata_reads += 1
                if self.metadata_reads == 2:
                    self.observed_counts.append(registry.snapshot().count)
                return stable_metadata

            def resolve_elements(
                self,
                variant_id: str,
                context: ReferenceContext,
            ) -> tuple[CandidateElement, ...]:
                return ()

            def collect_claims(
                self,
                variant_id: str,
                element_id: str,
                context: ReferenceContext,
            ) -> tuple[EvidenceClaim, ...]:
                return ()

        adapter = ReentrantMetadataAdapter()
        registry.register(adapter)

        self.assertEqual(adapter.observed_counts, [0])
        self.assertEqual(registry.snapshot().count, 1)

    def test_resolution_prefers_full_variant_and_retains_provenance(self) -> None:
        case = fixture_manifest()
        adapter = _VariantAdapter(_metadata(), case.candidate_elements)
        registry = AdapterRegistry()
        entry = registry.register(adapter)

        report = registry.resolve_manifest(case, (adapter.metadata.adapter_id,))

        self.assertEqual(adapter.seen, [case.variants[0]])
        self.assertEqual(report.elements, case.candidate_elements)
        self.assertEqual(report.element_count, 1)
        self.assertEqual(report.attribution_count, 1)
        self.assertEqual(report.manifest_address, case.content_address)
        self.assertEqual(report.items[0].metadata_address, entry.metadata_address)
        self.assertEqual(
            report.items[0].element_address,
            content_hash(case.candidate_elements[0].to_dict(), prefix="adapter-element"),
        )
        self.assertEqual(
            report.content_address,
            content_hash(report.body(), prefix="adapter-resolution"),
        )
        self.assertEqual(
            AdapterResolutionItem.from_dict(report.items[0].to_dict()),
            report.items[0],
        )
        self.assertEqual(AdapterResolutionReport.from_dict(report.to_dict()), report)

        forged_count = copy.deepcopy(report.to_dict())
        forged_count["element_count"] = 0
        with self.assertRaisesRegex(ValidationError, "element_count is not derived"):
            AdapterResolutionReport.from_dict(forged_count)
        forged_item = copy.deepcopy(report.to_dict())
        forged_item["items"][0]["element_address"] = "adapter-element:" + "0" * 64
        with self.assertRaisesRegex(ValidationError, "element address"):
            AdapterResolutionReport.from_dict(forged_item)
        unknown = copy.deepcopy(report.to_dict())
        unknown["unknown"] = True
        with self.assertRaisesRegex(ValidationError, "fields are not exact"):
            AdapterResolutionReport.from_dict(unknown)

        with self.assertRaisesRegex(ValidationError, "hard adapter ceiling"):
            AdapterResolutionReport(
                registry_address=report.registry_address,
                manifest_address=report.manifest_address,
                context_address=report.context_address,
                adapter_ids=tuple(f"adapter-{index:03}" for index in range(65)),
                variant_ids=report.variant_ids,
                items=(),
            )
        with self.assertRaisesRegex(ValidationError, "hard item ceiling"):
            AdapterResolutionReport(
                registry_address=report.registry_address,
                manifest_address=report.manifest_address,
                context_address=report.context_address,
                adapter_ids=report.adapter_ids,
                variant_ids=report.variant_ids,
                items=(report.items[0],) * 100_001,
            )
        self.assertEqual(
            registry.resolve_for_manifest(case, (adapter.metadata.adapter_id,)),
            case.candidate_elements,
        )

    def test_resolution_item_constructor_has_a_private_hard_byte_ceiling(self) -> None:
        case = fixture_manifest()
        metadata = _metadata()
        oversized = replace(
            case.candidate_elements[0],
            annotations={"payload": "x" * (1024 * 1024)},
        )
        with self.assertRaisesRegex(ValidationError, "byte ceiling"):
            AdapterResolutionItem(
                adapter_id=metadata.adapter_id,
                metadata_address=metadata.content_address,
                variant_id=case.variants[0].variant_id,
                variant_address=content_hash(case.variants[0].to_dict(), prefix="adapter-variant"),
                element=oversized,
            )

    def test_legacy_resolver_remains_supported(self) -> None:
        case = fixture_manifest()
        legacy_metadata = _metadata(source_ids=())
        static = StaticElementAdapter(legacy_metadata, case.candidate_elements)
        self.assertEqual(
            static.metadata.source_ids,
            (case.candidate_elements[0].source_id,),
        )
        adapter = _LegacyAdapter(static.metadata, case.candidate_elements)
        registry = AdapterRegistry()
        registry.register(adapter)
        self.assertEqual(
            registry.resolve_for_manifest(case, (adapter.metadata.adapter_id,)),
            case.candidate_elements,
        )
        self.assertEqual(adapter.variant_ids, [case.variants[0].variant_id])

    def test_static_adapter_validates_construction_and_direct_arguments(self) -> None:
        case = fixture_manifest()
        malformed = copy.copy(case.candidate_elements[0])
        object.__setattr__(malformed, "start", True)
        with self.assertRaises(ValidationError):
            StaticElementAdapter(_metadata(), (malformed,))

        adapter = StaticElementAdapter(_metadata(), case.candidate_elements)
        unsupported = replace(case.context, disease_class="other")
        with self.assertRaisesRegex(ValidationError, "does not support"):
            adapter.resolve_elements(case.variants[0].variant_id, unsupported)
        with self.assertRaises(ValidationError):
            adapter.resolve_elements("", case.context)
        with self.assertRaises(ValidationError):
            adapter.collect_claims(
                case.variants[0].variant_id,
                "",
                case.context,
            )

    def test_registration_rejects_missing_or_shadowed_callables(self) -> None:
        metadata = _metadata()

        class BrokenAdapter:
            def __init__(self) -> None:
                self.metadata = metadata
                self.resolve_elements = ()
                self.collect_claims = ()

        with self.assertRaisesRegex(ValidationError, "callable"):
            AdapterRegistry().register(BrokenAdapter())  # type: ignore[arg-type]

    def test_wrong_container_and_item_types_fail_closed(self) -> None:
        case = fixture_manifest()
        for result in ([case.candidate_elements[0]], (object(),)):
            with self.subTest(result_type=type(result).__name__):
                registry = AdapterRegistry()
                metadata = _metadata()
                registry.register(_VariantAdapter(metadata, result))
                with self.assertRaises(ValidationError):
                    registry.resolve_manifest(case, (metadata.adapter_id,))

    def test_context_and_source_escape_fail_closed(self) -> None:
        case = fixture_manifest()
        element = case.candidate_elements[0]
        other_context = replace(element.context, disease_class="other")
        escaped = (
            replace(element, context=other_context),
            replace(element, source_id="undeclared-source"),
        )
        for returned in escaped:
            with self.subTest(returned=returned.to_dict()):
                registry = AdapterRegistry()
                metadata = _metadata()
                registry.register(_VariantAdapter(metadata, (returned,)))
                with self.assertRaises(ValidationError):
                    registry.resolve_manifest(case, (metadata.adapter_id,))

    def test_duplicate_conflict_and_overages_do_not_partially_resolve(self) -> None:
        case = fixture_manifest()
        element = case.candidate_elements[0]
        duplicate_registry = AdapterRegistry()
        duplicate_metadata = _metadata()
        duplicate_registry.register(_VariantAdapter(duplicate_metadata, (element, element)))
        with self.assertRaisesRegex(ValidationError, "duplicate"):
            duplicate_registry.resolve_manifest(case, (duplicate_metadata.adapter_id,))

        conflict_registry = AdapterRegistry()
        first_metadata = _metadata("first")
        second_metadata = _metadata("second")
        conflict_registry.register(_VariantAdapter(first_metadata, (element,)))
        conflict_registry.register(
            _VariantAdapter(
                second_metadata,
                (replace(element, features={"changed": 1.0}),),
            )
        )
        with self.assertRaisesRegex(ValidationError, "conflicting"):
            conflict_registry.resolve_manifest(case, ("second", "first"))

        bounded_registry = AdapterRegistry(
            AdapterLimits(max_elements_per_variant=1, max_elements_total=1)
        )
        bounded_metadata = _metadata()
        bounded_registry.register(_VariantAdapter(bounded_metadata, (element, element)))
        with self.assertRaises(ValidationError):
            bounded_registry.resolve_manifest(case, (bounded_metadata.adapter_id,))

    def test_total_element_exhaustion_stops_later_adapter_resolvers(self) -> None:
        case = fixture_manifest()
        first = _VariantAdapter(_metadata("first"), case.candidate_elements)
        second = _VariantAdapter(_metadata("second"), case.candidate_elements)
        registry = AdapterRegistry(AdapterLimits(max_elements_total=1))
        registry.register(first)
        registry.register(second)

        with self.assertRaisesRegex(ValidationError, "total element ceiling"):
            registry.resolve_manifest(case, ("first", "second"))
        self.assertEqual(len(first.seen), 1)
        self.assertEqual(second.seen, [])

    def test_resolution_report_limit_accounts_for_items_commas_and_count_digits(
        self,
    ) -> None:
        case = fixture_manifest()
        base = case.candidate_elements[0]
        first_elements = tuple(
            replace(
                base,
                element_id=f"a-element-{index:02d}",
                start=base.start + index,
                end=base.end + index,
            )
            for index in range(10)
        )
        second_elements = (
            replace(
                base,
                element_id="z-element",
                start=base.start + 20,
                end=base.end + 20,
            ),
        )
        first_metadata = _metadata("a-first")
        second_metadata = _metadata("z-second")
        probe = AdapterRegistry()
        probe.register(_VariantAdapter(first_metadata, first_elements))
        probe.register(_VariantAdapter(second_metadata, second_elements))
        probe_report = probe.resolve_manifest(case, ("a-first", "z-second"))
        first_items = tuple(item for item in probe_report.items if item.adapter_id == "a-first")
        ten_item_report = replace(
            probe_report,
            items=first_items,
            content_address="",
        )
        ten_item_size = len(canonical_bytes(ten_item_report.to_dict()))

        first = _VariantAdapter(first_metadata, first_elements)
        second = _VariantAdapter(second_metadata, second_elements)
        registry = AdapterRegistry(AdapterLimits(max_report_bytes=ten_item_size - 1))
        registry.register(first)
        registry.register(second)
        with self.assertRaisesRegex(ValidationError, "report byte ceiling"):
            registry.resolve_manifest(case, ("a-first", "z-second"))

        self.assertEqual(len(first.seen), 1)
        self.assertEqual(second.seen, [])

    def test_fixed_report_overhead_is_checked_before_adapter_callbacks(self) -> None:
        case = fixture_manifest()
        probe_adapter = _VariantAdapter(_metadata("tiny-report"), ())
        probe_registry = AdapterRegistry()
        probe_registry.register(probe_adapter)
        empty_resolution = probe_registry.resolve_manifest(
            case,
            (probe_adapter.metadata.adapter_id,),
        )
        empty_resolution_size = len(canonical_bytes(empty_resolution.to_dict()))

        tiny_adapter = _VariantAdapter(_metadata("tiny-report"), ())
        tiny_registry = AdapterRegistry(AdapterLimits(max_report_bytes=empty_resolution_size - 1))
        tiny_registry.register(tiny_adapter)
        with self.assertRaisesRegex(ValidationError, "report.*byte ceiling"):
            tiny_registry.resolve_manifest(case, (tiny_adapter.metadata.adapter_id,))
        self.assertEqual(tiny_adapter.seen, [])

        claim_probe_adapter = _VariantAdapter(
            _metadata("claim-shell"),
            case.candidate_elements,
        )
        claim_probe_registry = AdapterRegistry()
        claim_probe_registry.register(claim_probe_adapter)
        probe_resolution = claim_probe_registry.resolve_manifest(
            case,
            (claim_probe_adapter.metadata.adapter_id,),
        )
        minimum_claim_report = claim_probe_registry.collect_claims(
            case,
            probe_resolution,
        )
        minimum_claim_report_size = len(canonical_bytes(minimum_claim_report.to_dict()))

        bounded_adapter = _VariantAdapter(_metadata("claim-shell"), case.candidate_elements)
        bounded_registry = AdapterRegistry(
            AdapterLimits(max_report_bytes=minimum_claim_report_size - 1)
        )
        bounded_registry.register(bounded_adapter)
        bounded_resolution = bounded_registry.resolve_manifest(
            case,
            (bounded_adapter.metadata.adapter_id,),
        )
        with self.assertRaisesRegex(ValidationError, "claim collection report.*byte ceiling"):
            bounded_registry.collect_claims(case, bounded_resolution)
        self.assertEqual(bounded_adapter.claim_seen, [])

    def test_claim_report_limit_accounts_for_shell_replacement_and_count_digits(
        self,
    ) -> None:
        case = fixture_manifest()
        base = case.candidate_elements[0]
        first_element = replace(base, element_id="a-element")
        second_element = replace(
            base,
            element_id="z-element",
            start=base.start + 1,
            end=base.end + 1,
        )
        metadata = _metadata("claim-growth")
        first_claims = tuple(
            _claim(f"progressive-{index}", adapter_id=metadata.adapter_id) for index in range(10)
        )
        claim_results = {first_element.element_id: first_claims}
        probe_adapter = _VariantAdapter(
            metadata,
            (first_element, second_element),
            claim_results=claim_results,
        )
        probe_registry = AdapterRegistry()
        probe_registry.register(probe_adapter)
        probe_resolution = probe_registry.resolve_manifest(
            case,
            (metadata.adapter_id,),
        )
        progressive_report = probe_registry.collect_claims(case, probe_resolution)
        progressive_size = len(canonical_bytes(progressive_report.to_dict()))

        bounded_adapter = _VariantAdapter(
            metadata,
            (first_element, second_element),
            claim_results=claim_results,
        )
        bounded_registry = AdapterRegistry(AdapterLimits(max_report_bytes=progressive_size - 1))
        bounded_registry.register(bounded_adapter)
        bounded_resolution = bounded_registry.resolve_manifest(
            case,
            (metadata.adapter_id,),
        )
        with self.assertRaisesRegex(ValidationError, "report byte ceiling"):
            bounded_registry.collect_claims(case, bounded_resolution)
        self.assertEqual(
            bounded_adapter.claim_seen,
            [(case.variants[0].variant_id, first_element.element_id)],
        )

    def test_per_edge_claim_allowances_are_progressive_and_missing_means_zero(
        self,
    ) -> None:
        case = fixture_manifest()
        base = case.candidate_elements[0]
        first_element = replace(base, element_id="a-element")
        second_element = replace(
            base,
            element_id="z-element",
            start=base.start + 1,
            end=base.end + 1,
        )
        gene_id = base.target_genes[0] if base.target_genes else base.element_id
        state_id = base.state_ids[0] if base.state_ids else "unresolved_state"
        digest = content_hash(
            {"source": gene_id, "target": state_id, "type": "gene_to_state"}
        ).split(":", 1)[1]
        shared_edge_id = f"edge-{digest[:20]}"
        metadata = _metadata("edge-budget")
        adapter = _VariantAdapter(
            metadata,
            (first_element, second_element),
            claim_results={
                first_element.element_id: (
                    _claim(
                        "first-edge-claim",
                        adapter_id=metadata.adapter_id,
                        edge_id=shared_edge_id,
                    ),
                ),
                second_element.element_id: (
                    _claim(
                        "second-edge-claim",
                        adapter_id=metadata.adapter_id,
                        edge_id=shared_edge_id,
                    ),
                ),
            },
        )
        registry = AdapterRegistry()
        registry.register(adapter)
        resolution = registry.resolve_manifest(case, (metadata.adapter_id,))
        possible_edges = set().union(
            *(
                adapters_module._resolution_item_edge_ids(  # noqa: SLF001
                    item.variant_id,
                    item.element,
                )
                for item in resolution.items
            )
        )
        edge_allowances = {edge_id: 1 for edge_id in possible_edges}

        with self.assertRaisesRegex(ValidationError, "per-edge claim ceiling"):
            registry.collect_claims(
                case,
                resolution,
                max_claims_by_edge=edge_allowances,
            )
        self.assertEqual(
            adapter.claim_seen,
            [(case.variants[0].variant_id, first_element.element_id)],
        )

        adapter.claim_seen.clear()
        with self.assertRaisesRegex(ValidationError, "per-edge claim ceiling"):
            registry.collect_claims(case, resolution, max_claims_by_edge={})
        self.assertEqual(adapter.claim_seen, [])

        with self.assertRaisesRegex(ValidationError, "max_claims_by_edge values"):
            registry.collect_claims(
                case,
                resolution,
                max_claims_by_edge={shared_edge_id: True},
            )

    def test_per_edge_allowance_map_covers_the_full_valid_graph_surface(self) -> None:
        case = fixture_manifest()
        metadata = _metadata("edge-surface")
        adapter = _VariantAdapter(metadata, ())
        registry = AdapterRegistry()
        registry.register(adapter)
        resolution = registry.resolve_manifest(case, (metadata.adapter_id,))
        full_edge_surface = {f"edge-{index:05d}": 1 for index in range(20_000)}

        report = registry.collect_claims(
            case,
            resolution,
            max_claims_by_edge=full_edge_surface,
        )
        self.assertEqual(report.claim_count, 0)
        self.assertEqual(registry.limits.max_claims_total, 10_000)

        oversized_surface = full_edge_surface | {"edge-overflow": 1}
        with self.assertRaisesRegex(ValidationError, "item ceiling"):
            registry.collect_claims(
                case,
                resolution,
                max_claims_by_edge=oversized_surface,
            )

        class LyingEdgeMap(Mapping[str, int]):
            def __init__(self) -> None:
                self.yielded = 0

            def __getitem__(self, key: str) -> int:
                return 1

            def __iter__(self) -> Iterator[str]:
                for index in range(20_001):
                    self.yielded += 1
                    yield f"edge-hostile-{index:05d}"

            def __len__(self) -> int:
                return 0

        lying_surface = LyingEdgeMap()
        with self.assertRaisesRegex(ValidationError, "item ceiling"):
            registry.collect_claims(
                case,
                resolution,
                max_claims_by_edge=lying_surface,
            )
        self.assertEqual(lying_surface.yielded, 20_001)

    def test_foreign_claim_edge_is_rejected_on_every_public_collection_path(self) -> None:
        case = fixture_manifest()
        element = case.candidate_elements[0]
        metadata = _metadata("foreign-edge")
        adapter = _VariantAdapter(
            metadata,
            (element,),
            claim_results={
                element.element_id: (
                    _claim(
                        "foreign-edge",
                        adapter_id=metadata.adapter_id,
                        edge_id="edge-foreign",
                    ),
                )
            },
        )
        registry = AdapterRegistry()
        registry.register(adapter)
        resolution = registry.resolve_manifest(case, (metadata.adapter_id,))
        owned_edges = adapters_module._resolution_item_edge_ids(  # noqa: SLF001
            resolution.items[0].variant_id,
            resolution.items[0].element,
        )

        with self.assertRaisesRegex(ValidationError, "does not belong"):
            registry.collect_claims(case, resolution)

        snapshot, entries = registry.selected_entries((metadata.adapter_id,))
        captured_resolution = registry.resolve_manifest_entries(case, snapshot, entries)
        with self.assertRaisesRegex(ValidationError, "does not belong"):
            registry.collect_claims_entries(
                case,
                captured_resolution,
                snapshot,
                entries,
            )

        with self.assertRaisesRegex(ValidationError, "does not belong"):
            registry.collect_claims(
                case,
                resolution,
                max_claims_by_edge={edge_id: 1 for edge_id in owned_edges},
            )
        self.assertEqual(len(adapter.claim_seen), 3)

    def test_after_callback_stops_resolution_and_collection_at_the_boundary(
        self,
    ) -> None:
        case = fixture_manifest()
        first = _VariantAdapter(_metadata("a-first"), case.candidate_elements)
        second = _VariantAdapter(_metadata("z-second"), case.candidate_elements)
        registry = AdapterRegistry()
        registry.register(first)
        registry.register(second)

        def reject_drift() -> None:
            raise ValidationError("configuration drift")

        with self.assertRaisesRegex(ValidationError, "configuration drift"):
            registry.resolve_manifest(
                case,
                ("a-first", "z-second"),
                after_callback=reject_drift,
            )
        self.assertEqual(len(first.seen), 1)
        self.assertEqual(second.seen, [])

        collector = _VariantAdapter(_metadata("collector"), case.candidate_elements)
        claim_registry = AdapterRegistry()
        claim_registry.register(collector)
        resolution = claim_registry.resolve_manifest(case, ("collector",))
        with self.assertRaisesRegex(ValidationError, "configuration drift"):
            claim_registry.collect_claims(
                case,
                resolution,
                after_callback=reject_drift,
            )
        self.assertEqual(len(collector.claim_seen), 1)

        collector.claim_seen.clear()
        with self.assertRaisesRegex(ValidationError, "after_callback must be callable"):
            claim_registry.collect_claims(
                case,
                resolution,
                after_callback=object(),  # type: ignore[arg-type]
            )
        self.assertEqual(collector.claim_seen, [])

    def test_missing_source_declaration_and_metadata_drift_fail_closed(self) -> None:
        case = fixture_manifest()
        no_sources = _metadata(source_ids=())
        registry = AdapterRegistry()
        registry.register(_VariantAdapter(no_sources, case.candidate_elements))
        with self.assertRaisesRegex(ValidationError, "does not declare source"):
            registry.resolve_manifest(case, (no_sources.adapter_id,))

        metadata = _metadata("drifting")
        adapter = _VariantAdapter(metadata, case.candidate_elements)
        registry = AdapterRegistry()
        registry.register(adapter)
        adapter.metadata = replace(metadata, version="2026.09", content_address="")
        with self.assertRaisesRegex(ValidationError, "metadata drift"):
            registry.get(metadata.adapter_id)

        metadata = _metadata("during-call")
        adapter = _VariantAdapter(metadata, case.candidate_elements, drift_during_call=True)
        registry = AdapterRegistry()
        registry.register(adapter)
        with self.assertRaisesRegex(ValidationError, "metadata drift"):
            registry.resolve_manifest(case, (metadata.adapter_id,))

    def test_resolution_rechecks_later_adapter_metadata_before_its_callback(self) -> None:
        case = fixture_manifest()
        later = _VariantAdapter(_metadata("z-later"), case.candidate_elements)

        class MutatingEarlierAdapter(_VariantAdapter):
            def resolve_variant_elements(
                self,
                variant: VariantIdentity,
                context: ReferenceContext,
            ) -> Any:
                result = super().resolve_variant_elements(variant, context)
                later.metadata = replace(
                    later.metadata,
                    version="2026.09",
                    content_address="",
                )
                return result

        earlier = MutatingEarlierAdapter(_metadata("a-earlier"), ())
        registry = AdapterRegistry()
        registry.register(earlier)
        registry.register(later)

        with self.assertRaisesRegex(ValidationError, "metadata drift"):
            registry.resolve_manifest(case, ("a-earlier", "z-later"))
        self.assertEqual(len(earlier.seen), 1)
        self.assertEqual(later.seen, [])

    def test_resolution_checks_metadata_before_dynamic_resolver_attribute_access(
        self,
    ) -> None:
        case = fixture_manifest()

        class DynamicResolverAdapter(_VariantAdapter):
            def __init__(self) -> None:
                super().__init__(_metadata("z-dynamic"), ())
                self.metadata_was_checked = False
                self.checks_seen_at_resolver_access: list[bool] = []

            def __getattribute__(self, name: str) -> Any:
                if name == "metadata":
                    object.__setattr__(self, "metadata_was_checked", True)
                elif name == "resolve_variant_elements":
                    checked = object.__getattribute__(self, "metadata_was_checked")
                    object.__getattribute__(
                        self,
                        "checks_seen_at_resolver_access",
                    ).append(checked)
                    object.__setattr__(self, "metadata_was_checked", False)
                return object.__getattribute__(self, name)

        later = DynamicResolverAdapter()

        class ClearingEarlierAdapter(_VariantAdapter):
            def resolve_variant_elements(
                self,
                variant: VariantIdentity,
                context: ReferenceContext,
            ) -> Any:
                result = super().resolve_variant_elements(variant, context)
                object.__setattr__(later, "metadata_was_checked", False)
                return result

        earlier = ClearingEarlierAdapter(_metadata("a-earlier-dynamic"), ())
        registry = AdapterRegistry()
        registry.register(earlier)
        registry.register(later)
        later.checks_seen_at_resolver_access.clear()
        object.__setattr__(later, "metadata_was_checked", False)

        registry.resolve_manifest(case, ("a-earlier-dynamic", "z-dynamic"))

        self.assertEqual(later.checks_seen_at_resolver_access, [True])

    def test_selected_adapter_and_item_byte_limits_apply_before_report(self) -> None:
        case = fixture_manifest()
        metadata = _metadata()
        registry = AdapterRegistry(AdapterLimits(max_selected_adapters=1))
        registry.register(_VariantAdapter(metadata, case.candidate_elements))
        with self.assertRaisesRegex(ValidationError, "unique"):
            registry.resolve_manifest(case, (metadata.adapter_id, metadata.adapter_id))

        tiny = AdapterRegistry(AdapterLimits(max_item_bytes=1))
        tiny.register(_VariantAdapter(metadata, case.candidate_elements))
        with self.assertRaisesRegex(ValidationError, "byte ceiling"):
            tiny.resolve_manifest(case, (metadata.adapter_id,))


if __name__ == "__main__":
    unittest.main()
