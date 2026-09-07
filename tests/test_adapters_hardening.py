"""Adversarial coverage for the executable adapter boundary."""

from __future__ import annotations

import copy
import unittest
from dataclasses import replace
from threading import Thread
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
    StaticElementAdapter,
)
from glio_noncode.errors import ValidationError
from glio_noncode.models import CandidateElement, ReferenceContext, VariantIdentity
from glio_noncode.serialization import content_hash

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


class _VariantAdapter:
    def __init__(
        self,
        metadata: AdapterMetadata,
        result: Any,
        *,
        drift_during_call: bool = False,
    ) -> None:
        self.metadata = metadata
        self.result = result
        self.drift_during_call = drift_during_call
        self.seen: list[VariantIdentity] = []

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
        return ()


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
        malformed = replace(case.candidate_elements[0], start=True)
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
