"""Adversarial coverage for bounded adapter claim collection."""

from __future__ import annotations

import copy
import unittest
from dataclasses import replace
from typing import Any

from glio_noncode.adapters import (
    ADAPTER_HARD_MAX_CLAIMS_TOTAL,
    AdapterClaimAttribution,
    AdapterClaimCollectionReport,
    AdapterLimits,
    AdapterMetadata,
    AdapterRegistry,
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
from glio_noncode.serialization import content_hash

from .helpers import fixture_manifest


def metadata(
    adapter_id: str = "claim-adapter",
    *,
    source_ids: tuple[str, ...] = ("fixture-atlas-001",),
    channels: tuple[str, ...] = ("external_signal",),
) -> AdapterMetadata:
    manifest = fixture_manifest()
    return AdapterMetadata(
        adapter_id=adapter_id,
        display_name=f"Claim adapter {adapter_id}",
        version="2026.09",
        license="synthetic-fixture",
        data_access="local_fixture",
        supported_contexts=(manifest.context.key,),
        channels=channels,
        failure_modes=("empty_result", "upstream_failure"),
        validation_status="integration-tested",
        source_ids=source_ids,
    )


def claim(
    label: str,
    *,
    context: ReferenceContext | None = None,
    edge_id: str | None = None,
    source_id: str = "fixture-atlas-001",
    channel: str = "external_signal",
    evidence_id: str | None = None,
    depends_on: tuple[str, ...] = (),
    produced_by: str = "claim-adapter",
) -> EvidenceClaim:
    manifest = fixture_manifest()
    element = manifest.candidate_elements[0]
    gene_id = element.target_genes[0] if element.target_genes else element.element_id
    state_id = element.state_ids[0] if element.state_ids else "unresolved_state"
    shared_edge_digest = content_hash(
        {"source": gene_id, "target": state_id, "type": "gene_to_state"}
    ).split(":", 1)[1]
    return EvidenceClaim(
        evidence_id=evidence_id
        or content_hash({"kind": "adapter-claim", "label": label}, prefix="claim"),
        edge_id=edge_id or f"edge-{shared_edge_digest[:20]}",
        source_id=source_id,
        channel=channel,
        state=EvidenceState.SUPPORTED,
        tier=EvidenceTier.REFERENCE,
        score=0.83,
        confidence=0.91,
        context=manifest.context if context is None else context,
        summary=f"External adapter evidence for {label}.",
        payload={"label": label},
        depends_on=depends_on,
        produced_by=produced_by,
        created_at="2026-09-03T12:00:00+00:00",
    )


class ClaimAdapter:
    def __init__(
        self,
        adapter_metadata: AdapterMetadata,
        elements: tuple[CandidateElement, ...],
        results: dict[str, Any] | None = None,
        *,
        drift_during_collection: bool = False,
        fail_collection: bool = False,
        mutate_context: bool = False,
    ) -> None:
        self.metadata = adapter_metadata
        self.elements = elements
        self.results = {} if results is None else results
        self.drift_during_collection = drift_during_collection
        self.fail_collection = fail_collection
        self.mutate_context = mutate_context
        self.collect_calls: list[tuple[str, str, ReferenceContext]] = []

    def resolve_variant_elements(
        self,
        variant: VariantIdentity,
        context: ReferenceContext,
    ) -> tuple[CandidateElement, ...]:
        return self.elements

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
    ) -> Any:
        self.collect_calls.append((variant_id, element_id, context))
        if self.drift_during_collection:
            self.metadata = replace(
                self.metadata,
                version="2026.10",
                content_address="",
            )
        if self.mutate_context:
            object.__setattr__(context, "cell_state", "mutated-cell-state")
        if self.fail_collection:
            raise RuntimeError("upstream failed")
        return self.results.get(element_id, ())


def registered(
    adapter: ClaimAdapter,
    *,
    limits: AdapterLimits | None = None,
):
    manifest = fixture_manifest()
    registry = AdapterRegistry(limits)
    registry.register(adapter)
    resolution = registry.resolve_manifest(manifest, (adapter.metadata.adapter_id,))
    return manifest, registry, resolution


class AdapterClaimCollectionTests(unittest.TestCase):
    def test_factorized_gene_state_edge_can_belong_to_multiple_resolution_items(
        self,
    ) -> None:
        manifest = fixture_manifest()
        first = manifest.candidate_elements[0]
        second = replace(
            first,
            element_id="shared-gene-state-element",
            start=first.start + 1,
            end=first.end + 1,
        )
        gene_id = first.target_genes[0] if first.target_genes else first.element_id
        state_id = first.state_ids[0] if first.state_ids else "unresolved_state"
        digest = content_hash(
            {"source": gene_id, "target": state_id, "type": "gene_to_state"}
        ).split(":", 1)[1]
        shared_edge_id = f"edge-{digest[:20]}"
        evidence = claim("shared-gene-state", edge_id=shared_edge_id)
        adapter = ClaimAdapter(
            metadata(),
            (first, second),
            {first.element_id: (evidence,), second.element_id: ()},
        )
        manifest, registry, resolution = registered(adapter)

        report = registry.collect_claims(manifest, resolution)
        report.validate_claim_ownership(resolution)
        self.assertEqual(report.claims, (evidence,))
        self.assertEqual(len(resolution.items), 2)

    def test_report_is_addressed_strict_and_fully_attributed(self) -> None:
        manifest = fixture_manifest()
        element = manifest.candidate_elements[0]
        evidence = claim("happy")
        adapter = ClaimAdapter(metadata(), (element,), {element.element_id: (evidence,)})
        manifest, registry, resolution = registered(adapter)

        report = registry.collect_claims(manifest, resolution)

        self.assertEqual(report.registry_snapshot, registry.snapshot())
        self.assertEqual(report.adapter_metadata, (adapter.metadata,))
        self.assertEqual(report.registry_address, resolution.registry_address)
        self.assertEqual(report.manifest_address, manifest.content_address)
        self.assertEqual(report.context, manifest.context)
        self.assertEqual(
            report.context_address,
            content_hash(manifest.context.to_dict(), prefix="adapter-context"),
        )
        self.assertEqual(report.adapter_ids, resolution.adapter_ids)
        self.assertEqual(report.variant_ids, resolution.variant_ids)
        self.assertEqual(report.resolution_address, resolution.content_address)
        self.assertEqual(report.attribution_count, 1)
        self.assertEqual(report.claim_count, 1)
        self.assertEqual(report.claims, (evidence,))
        attribution = report.attributions[0]
        resolution_item = resolution.items[0]
        self.assertEqual(attribution.identity, resolution_item.identity)
        self.assertEqual(attribution.metadata_address, resolution_item.metadata_address)
        self.assertEqual(attribution.variant_address, resolution_item.variant_address)
        self.assertEqual(attribution.element_address, resolution_item.element_address)
        self.assertEqual(
            attribution.resolution_item_address,
            resolution_item.content_address,
        )
        self.assertEqual(adapter.collect_calls[0][:2], resolution_item.identity[1:])
        self.assertEqual(adapter.collect_calls[0][2], manifest.context)
        self.assertIsNot(adapter.collect_calls[0][2], manifest.context)
        self.assertEqual(
            report.content_address,
            content_hash(report.body(), prefix="adapter-claim-collection"),
        )
        self.assertEqual(
            AdapterClaimAttribution.from_dict(attribution.to_dict()),
            attribution,
        )
        self.assertEqual(AdapterClaimCollectionReport.from_dict(report.to_dict()), report)

        forged_count = copy.deepcopy(report.to_dict())
        forged_count["claim_count"] = 0
        with self.assertRaisesRegex(ValidationError, "claim_count is not derived"):
            AdapterClaimCollectionReport.from_dict(forged_count)
        forged_address = copy.deepcopy(report.to_dict())
        forged_address["attributions"][0]["element_id"] = "forged-element"
        with self.assertRaisesRegex(ValidationError, "address does not match"):
            AdapterClaimCollectionReport.from_dict(forged_address)
        unknown = copy.deepcopy(report.to_dict())
        unknown["unexpected"] = True
        with self.assertRaisesRegex(ValidationError, "fields are not exact"):
            AdapterClaimCollectionReport.from_dict(unknown)
        missing_metadata = copy.deepcopy(report.to_dict())
        missing_metadata["adapter_metadata"] = []
        with self.assertRaisesRegex(ValidationError, "exactly cover selected adapter IDs"):
            AdapterClaimCollectionReport.from_dict(missing_metadata)
        forged_metadata = copy.deepcopy(report.to_dict())
        forged_metadata["adapter_metadata"][0]["license"] = "forged-license"
        with self.assertRaisesRegex(ValidationError, "content address does not match"):
            AdapterClaimCollectionReport.from_dict(forged_metadata)

    def test_collectors_are_called_only_for_their_attributed_resolution_items(self) -> None:
        manifest = fixture_manifest()
        element = manifest.candidate_elements[0]
        first = ClaimAdapter(
            metadata("first"),
            (element,),
            {element.element_id: (claim("first", produced_by="first"),)},
        )
        second = ClaimAdapter(metadata("second"), ())
        registry = AdapterRegistry()
        registry.register(second)
        registry.register(first)
        resolution = registry.resolve_manifest(manifest, ("second", "first"))

        report = registry.collect_claims(manifest, resolution)

        self.assertEqual(report.adapter_ids, ("first", "second"))
        self.assertEqual(tuple(item.adapter_id for item in report.attributions), ("first",))
        self.assertEqual(len(first.collect_calls), 1)
        self.assertEqual(second.collect_calls, [])

    def test_exact_tuple_per_element_and_total_claim_limits_fail_closed(self) -> None:
        manifest = fixture_manifest()
        element = manifest.candidate_elements[0]
        wrong_container = ClaimAdapter(
            metadata(),
            (element,),
            {element.element_id: [claim("list-result")]},
        )
        manifest, registry, resolution = registered(wrong_container)
        with self.assertRaisesRegex(ValidationError, "exact tuple"):
            registry.collect_claims(manifest, resolution)

        over_element = ClaimAdapter(
            metadata(),
            (element,),
            {element.element_id: (claim("one"), claim("two"))},
        )
        manifest, registry, resolution = registered(
            over_element,
            limits=AdapterLimits(max_claims_per_element=1),
        )
        with self.assertRaisesRegex(ValidationError, "per-element ceiling"):
            registry.collect_claims(manifest, resolution)

        second_element = replace(
            element,
            element_id="second-element",
            start=element.start + 1,
            end=element.end + 1,
        )
        over_total = ClaimAdapter(
            metadata(),
            (element, second_element),
            {
                element.element_id: (claim("total-one"),),
                second_element.element_id: (claim("total-two"),),
            },
        )
        manifest, registry, resolution = registered(
            over_total,
            limits=AdapterLimits(max_claims_total=1),
        )
        with self.assertRaisesRegex(ValidationError, "total claim ceiling"):
            registry.collect_claims(manifest, resolution)
        self.assertEqual(len(over_total.collect_calls), 1)

        over_total.collect_calls.clear()
        with self.assertRaisesRegex(ValidationError, "total claim ceiling"):
            registry.collect_claims(manifest, resolution, max_claims=0)
        self.assertEqual(over_total.collect_calls, [])

        for malformed in (True, -1, 1.0, "1", ADAPTER_HARD_MAX_CLAIMS_TOTAL + 1):
            with self.subTest(max_claims=malformed), self.assertRaisesRegex(
                ValidationError,
                "adapter max_claims",
            ):
                registry.collect_claims(  # type: ignore[arg-type]
                    manifest,
                    resolution,
                    max_claims=malformed,
                )
        self.assertEqual(over_total.collect_calls, [])

    def test_total_claim_limit_is_exact_and_downward_only(self) -> None:
        for malformed in (True, 0, 1.0, "1", ADAPTER_HARD_MAX_CLAIMS_TOTAL + 1):
            with self.subTest(malformed=malformed), self.assertRaises(ValidationError):
                AdapterLimits(max_claims_total=malformed)  # type: ignore[arg-type]

    def test_claim_type_canonical_context_and_declarations_are_enforced(self) -> None:
        manifest = fixture_manifest()
        element = manifest.candidate_elements[0]
        malformed_results = (
            ((object(),), "exact EvidenceClaim"),
            ((replace(claim("bad-time"), created_at="not-utc"),), "ISO-8601 UTC"),
            (
                (
                    claim(
                        "wrong-context",
                        context=replace(manifest.context, source_version="other-source"),
                    ),
                ),
                "escaped the requested context",
            ),
            ((claim("wrong-source", source_id="undeclared-source"),), "declared sources"),
            ((claim("wrong-channel", channel="undeclared_channel"),), "declared channels"),
            ((claim("wrong-producer", produced_by="other-adapter"),), "producer"),
        )
        for result, message in malformed_results:
            with self.subTest(message=message):
                adapter = ClaimAdapter(
                    metadata(),
                    (element,),
                    {element.element_id: result},
                )
                manifest, registry, resolution = registered(adapter)
                with self.assertRaisesRegex(ValidationError, message):
                    registry.collect_claims(manifest, resolution)

    def test_duplicate_claim_ids_are_rejected_within_and_across_attributions(self) -> None:
        manifest = fixture_manifest()
        element = manifest.candidate_elements[0]
        duplicate = claim("duplicate")
        within = ClaimAdapter(
            metadata(),
            (element,),
            {element.element_id: (duplicate, duplicate)},
        )
        manifest, registry, resolution = registered(within)
        with self.assertRaisesRegex(ValidationError, "duplicate evidence ID"):
            registry.collect_claims(manifest, resolution)

        second_element = replace(
            element,
            element_id="duplicate-second-element",
            start=element.start + 1,
            end=element.end + 1,
        )
        across = ClaimAdapter(
            metadata(),
            (element, second_element),
            {
                element.element_id: (duplicate,),
                second_element.element_id: (duplicate,),
            },
        )
        manifest, registry, resolution = registered(across)
        with self.assertRaisesRegex(ValidationError, "globally unique"):
            registry.collect_claims(manifest, resolution)

    def test_invocation_failure_metadata_drift_and_context_mutation_fail_closed(self) -> None:
        manifest = fixture_manifest()
        element = manifest.candidate_elements[0]
        scenarios = (
            (
                ClaimAdapter(metadata(), (element,), fail_collection=True),
                "collection failed",
            ),
            (
                ClaimAdapter(metadata(), (element,), drift_during_collection=True),
                "metadata drift",
            ),
            (
                ClaimAdapter(metadata(), (element,), mutate_context=True),
                "mutated its claim invocation context",
            ),
        )
        for adapter, message in scenarios:
            with self.subTest(message=message):
                manifest, registry, resolution = registered(adapter)
                with self.assertRaisesRegex(ValidationError, message):
                    registry.collect_claims(manifest, resolution)

    def test_selected_snapshot_manifest_mismatch_and_report_byte_limit_fail_closed(self) -> None:
        manifest = fixture_manifest()
        element = manifest.candidate_elements[0]
        adapter = ClaimAdapter(
            metadata(),
            (element,),
            {element.element_id: (claim("stale"),)},
        )
        manifest, registry, resolution = registered(adapter)
        unrelated = ClaimAdapter(metadata("later"), ())
        registry.register(unrelated)
        report = registry.collect_claims(manifest, resolution)
        with self.assertRaisesRegex(ValidationError, "exactly cover selected adapter IDs"):
            replace(
                report,
                registry_snapshot=registry.snapshot(),
                registry_address="",
                content_address="",
            )
        unrelated.metadata = replace(
            unrelated.metadata,
            version="2026.10",
            content_address="",
        )
        report = registry.collect_claims(manifest, resolution)
        self.assertEqual(report.adapter_ids, (adapter.metadata.adapter_id,))
        self.assertEqual(
            tuple(item.adapter_id for item in report.registry_snapshot.adapters),
            (adapter.metadata.adapter_id,),
        )
        self.assertEqual(len(adapter.collect_calls), 2)
        with self.assertRaisesRegex(ValidationError, "metadata drift"):
            registry.snapshot()

        forged_item = replace(
            resolution.items[0],
            variant_address="adapter-variant:" + "0" * 64,
            content_address="",
        )
        forged_resolution = replace(
            resolution,
            items=(forged_item,),
            content_address="",
        )
        with self.assertRaisesRegex(ValidationError, "variant address"):
            forged_resolution.validate_manifest(manifest)

        fresh_adapter = ClaimAdapter(metadata(), (element,))
        manifest, registry, resolution = registered(fresh_adapter)
        different_manifest = replace(manifest, case_id="different-case")
        with self.assertRaisesRegex(ValidationError, "does not bind"):
            registry.collect_claims(different_manifest, resolution)
        self.assertEqual(fresh_adapter.collect_calls, [])

        normal_adapter = ClaimAdapter(
            metadata(),
            (element,),
            {element.element_id: (claim("byte-limit"),)},
        )
        manifest, normal_registry, resolution = registered(normal_adapter)
        tiny_adapter = ClaimAdapter(
            metadata(),
            (element,),
            {element.element_id: (claim("byte-limit"),)},
        )
        tiny_registry = AdapterRegistry(AdapterLimits(max_report_bytes=2_200))
        tiny_registry.register(tiny_adapter)
        with self.assertRaisesRegex(
            ValidationError,
            "adapter claim collection report exceeds its byte ceiling",
        ):
            tiny_registry.collect_claims(manifest, resolution)

    def test_resolution_attribution_must_match_the_captured_adapter_metadata(self) -> None:
        manifest = fixture_manifest()
        element = manifest.candidate_elements[0]
        first = ClaimAdapter(
            metadata("first"),
            (element,),
            {element.element_id: (claim("first-metadata"),)},
        )
        second = ClaimAdapter(metadata("second"), ())
        registry = AdapterRegistry()
        registry.register(first)
        registry.register(second)
        resolution = registry.resolve_manifest(manifest, ("first",))
        forged_item = replace(
            resolution.items[0],
            metadata_address=second.metadata.content_address,
            content_address="",
        )
        forged_resolution = replace(
            resolution,
            items=(forged_item,),
            content_address="",
        )

        with self.assertRaisesRegex(ValidationError, "metadata does not match"):
            registry.collect_claims(manifest, forged_resolution)
        self.assertEqual(first.collect_calls, [])


if __name__ == "__main__":
    unittest.main()
