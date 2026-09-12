from __future__ import annotations

import copy
import json
import math
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from itertools import repeat
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import glio_noncode._callback_isolation as callback_isolation_module
import glio_noncode.data_sources as data_sources_module
from glio_noncode.data_sources import (
    MAX_ENRICHED_ELEMENTS,
    MAX_REFERENCE_FEATURES,
    MAX_REFERENCE_RECEIPTS,
    MAX_REFERENCE_VARIANTS,
    MAX_REFERENCE_WARNINGS,
    EnrichmentResult,
    EnsemblRestClient,
    FetchReceipt,
    FetchStatus,
    PublicReferenceRetriever,
    ReferenceBundle,
    ReferenceRetrievalLimits,
    RetryPolicy,
    SequenceSlice,
    SourceAccess,
    SourceCache,
    SourceCatalog,
    SourceClient,
    SourceKind,
    SourceSpec,
    TransportResponse,
    UcscRestClient,
)
from glio_noncode.errors import (
    SourceError,
    SourceNotFoundError,
    SourceRateLimitError,
    ValidationError,
)
from glio_noncode.serialization import canonical_bytes, content_hash

from .helpers import fixture_manifest


class FakeTransport:
    def __init__(self, responses: dict[str, object]) -> None:
        self.responses = responses
        self.calls: list[str] = []

    def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        timeout_seconds: float,
    ) -> TransportResponse:
        self.calls.append(url)
        value = self.responses[url]
        if isinstance(value, bytes):
            body = value
            content_type = "text/plain"
        else:
            body = json.dumps(value).encode("utf-8")
            content_type = "application/json"
        return TransportResponse(200, url, {"content-type": content_type}, body, 0.001)


class SequenceTransport:
    def __init__(self, responses: list[TransportResponse]) -> None:
        self.responses = list(responses)
        self.calls: list[str] = []

    def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        timeout_seconds: float,
    ) -> TransportResponse:
        self.calls.append(url)
        return self.responses.pop(0)


def _response(status: int, url: str, body: bytes = b"{}") -> TransportResponse:
    return TransportResponse(status, url, {"content-type": "application/json"}, body, 0.001)


def _source(**overrides: object) -> SourceSpec:
    values: dict[str, object] = {
        "source_id": "SRC-ENSEMBL-REST",
        "name": "Ensembl",
        "kind": SourceKind.REFERENCE_ANNOTATION,
        "access": SourceAccess.PUBLIC_API,
        "base_url": "https://ensembl.example",
        "canonical_url": "https://ensembl.example/docs",
        "version": "fixture-1",
        "license": "fixture",
        "rate_limit_per_minute": 100_000,
        "max_region_bp": 5_000_000,
    }
    values.update(overrides)
    return SourceSpec(**values)  # type: ignore[arg-type]


def _catalog() -> SourceCatalog:
    return SourceCatalog(
        (
            _source(),
            SourceSpec(
                source_id="SRC-UCSC-REST",
                name="UCSC",
                kind=SourceKind.GENOME_BROWSER,
                access=SourceAccess.PUBLIC_API,
                base_url="https://ucsc.example",
                canonical_url="https://ucsc.example/docs",
                version="fixture-1",
                license="fixture",
                rate_limit_per_minute=100000,
                max_region_bp=10_000_000,
            ),
        )
    )


class DataSourceTests(unittest.TestCase):
    def test_json_response_is_cached_and_receipt_changes_state(self) -> None:
        catalog = _catalog()
        url = "https://ensembl.example/lookup/symbol/homo_sapiens/GENE?expand=1"
        transport = FakeTransport({url: {"id": "ENSG000001", "display_name": "GENE"}})
        with tempfile.TemporaryDirectory() as directory:
            client = SourceClient(catalog, cache_root=directory, transport=transport)
            first = EnsemblRestClient(client).lookup_symbol("GENE", expand=True)
            second = EnsemblRestClient(client).lookup_symbol("GENE", expand=True)
            self.assertEqual(first.receipt.status.value, "fetched")
            self.assertEqual(second.receipt.status.value, "cache_hit")
            self.assertEqual(len(transport.calls), 1)
            self.assertEqual(second.value["id"], "ENSG000001")

    def test_ucsc_sequence_uses_zero_based_start_and_preserves_receipt(self) -> None:
        catalog = _catalog()
        url = "https://ucsc.example/getData/sequence?chrom=chr7&end=200&genome=hg38&start=99"
        transport = FakeTransport({url: {"dna": "A" * 101, "start": 99, "end": 200}})
        with tempfile.TemporaryDirectory() as directory:
            payload = UcscRestClient(
                SourceClient(catalog, cache_root=directory, transport=transport)
            ).sequence("7", 100, 200, genome_build="GRCh38")
            self.assertEqual(payload.value["dna"], "A" * 101)
            self.assertEqual(
                urlsplit(transport.calls[0]).query,
                "chrom=chr7&end=200&genome=hg38&start=99",
            )

    def test_live_reference_retriever_converts_real_shaped_payloads_to_elements(self) -> None:
        catalog = _catalog()
        manifest = fixture_manifest()
        variant = manifest.variants[0]
        query_start = variant.start - 10
        query_end = variant.end + 10
        sequence_url = (
            "https://ucsc.example/getData/sequence?chrom=chr7"
            f"&end={query_end}&genome=hg38&start={query_start - 1}"
        )
        overlap_url = (
            "https://ensembl.example/overlap/region/homo_sapiens/"
            f"7:{query_start}-{query_end}?feature=gene&feature=motif&feature=regulatory"
        )
        transport = FakeTransport(
            {
                sequence_url: {"dna": "A" * (query_end - query_start + 1)},
                overlap_url: [
                    {
                        "feature_type": "gene",
                        "id": "ENSG000001",
                        "external_name": "GENE_A",
                        "start": query_start,
                        "end": query_end,
                    },
                    {
                        "feature_type": "regulatory",
                        "id": "ENSR000001",
                        "seq_region_name": "7",
                        "start": variant.start - 2,
                        "end": variant.end + 2,
                        "description": "enhancer",
                    },
                ],
            }
        )
        with tempfile.TemporaryDirectory() as directory:
            retriever = PublicReferenceRetriever(
                SourceClient(catalog, cache_root=directory, transport=transport),
                window_bp=10,
            )
            bundle = retriever.retrieve(variant, manifest.context)
            self.assertEqual(bundle.sequence.sequence, "A" * 21)
            self.assertEqual(bundle.elements[0].element_id, "ENSR000001")
            self.assertEqual(bundle.elements[0].target_genes, ("GENE_A",))
            self.assertEqual(len(bundle.receipts), 2)
            self.assertTrue(bundle.content_address.startswith("sha256:"))

    def test_reference_callback_mutation_is_atomic_restored_and_retryable(self) -> None:
        def replacement_scope_factory():
            retained = object()

            def replacement_scope():
                _ = retained
                yield

            return replacement_scope

        def replacement_retrieve(
            self,
            variant,
            context,
            *,
            window_bp=None,
            _external_integrity_guard=None,
        ):
            del self, variant, context, window_bp, _external_integrity_guard
            return "mutated retrieval"

        class MutatedRetriever(PublicReferenceRetriever):
            pass

        source_scope = cast(Any, data_sources_module.source_callback_scope)
        source_scope_dict = source_scope.__dict__
        source_scope_dict_items = tuple(source_scope_dict.items())
        source_scope_wrapped = source_scope.__wrapped__
        source_scope_wrapped_code = source_scope_wrapped.__code__
        isolation_error_type = callback_isolation_module.ValidationError
        replacement_scope = replacement_scope_factory()

        def restore_callback_scope() -> None:
            source_scope.__dict__ = source_scope_dict
            source_scope_dict.clear()
            source_scope_dict.update(dict(source_scope_dict_items))
            source_scope_wrapped.__code__ = source_scope_wrapped_code
            vars(callback_isolation_module)["ValidationError"] = isolation_error_type

        self.addCleanup(restore_callback_scope)

        class MutatingTransport:
            def __init__(self, *, raise_after_mutation: bool) -> None:
                self.raise_after_mutation = raise_after_mutation
                self.calls: list[str] = []
                self.mutate_once = True
                self.variant = None
                self.context = None
                self.retriever = None

            def request(self, method, url, headers, timeout_seconds):
                del method, headers, timeout_seconds
                self.calls.append(url)
                if self.mutate_once:
                    self.mutate_once = False
                    assert self.variant is not None
                    assert self.context is not None
                    assert self.retriever is not None
                    object.__setattr__(self.variant, "variant_id", "redirected-variant")
                    object.__setattr__(self.variant, "start", self.variant.start + 10)
                    object.__setattr__(self.variant, "end", self.variant.end + 10)
                    dict.__setitem__(
                        self.variant.annotations,
                        "base-dict-bypass",
                        True,
                    )
                    list.append(
                        self.variant.annotations["nested"],
                        "base-list-bypass",
                    )
                    object.__setattr__(self.variant, "annotations", {"poisoned": True})
                    object.__setattr__(self.context, "genome_build", "GRCh37")
                    object.__setattr__(self.context, "assay_support", ("poisoned",))
                    self.retriever.window_bp = 1
                    object.__setattr__(
                        self.retriever.limits,
                        "max_features_per_variant",
                        1,
                    )
                    self.retriever.client.timeout_seconds = 999.0
                    self.retriever.ensembl.client = object()
                    self.retriever.client.catalog._specs.clear()
                    for limiter in self.retriever.client._limiters.values():
                        limiter._next_allowed = 10**100
                    self.retriever.client._limiters.clear()
                    self.retriever.client.transport = object()
                    self.retriever.__class__ = MutatedRetriever
                    data_sources_module.EnsemblRestClient = object  # type: ignore[assignment]
                    PublicReferenceRetriever.retrieve.__code__ = replacement_retrieve.__code__
                    source_scope.__dict__ = {"__wrapped__": replacement_scope}
                    source_scope_wrapped.__code__ = replacement_scope.__code__
                    vars(callback_isolation_module)["ValidationError"] = RuntimeError
                    assert PublicReferenceRetriever.retrieve.__kwdefaults__ is not None
                    PublicReferenceRetriever.retrieve.__kwdefaults__["window_bp"] = 1
                    PublicReferenceRetriever.retrieve.__annotations__["return"] = str
                    ReferenceBundle.__dataclass_fields__["variant_id"].name = "mutated_id"
                    assert ReferenceBundle.__init__.__closure__ is not None
                    ReferenceBundle.__init__.__closure__[0].cell_contents = object
                    EnsemblRestClient.source_id = "SRC-POISONED"
                    UcscRestClient._assemblies.clear()
                    if self.raise_after_mutation:
                        raise SourceError("mutated transport failure")
                if "/getData/sequence" in url:
                    query = parse_qs(urlsplit(url).query)
                    length = int(query["end"][0]) - int(query["start"][0])
                    body = json.dumps({"dna": "A" * length}).encode("utf-8")
                else:
                    body = b"[]"
                return TransportResponse(
                    200,
                    url,
                    {"content-type": "application/json"},
                    body,
                    0.001,
                )

        for raise_after_mutation in (False, True):
            with self.subTest(raise_after_mutation=raise_after_mutation):
                manifest = fixture_manifest()
                variant = replace(
                    manifest.variants[0],
                    annotations=dict(manifest.variants[0].annotations)
                    | {"nested": ["retained"]},
                )
                context = manifest.context
                variant_before = copy.deepcopy(variant.to_dict())
                context_before = copy.deepcopy(context.to_dict())
                annotations_alias = variant.annotations
                nested_annotations_alias = variant.annotations["nested"]
                transport = MutatingTransport(
                    raise_after_mutation=raise_after_mutation,
                )
                retrieve_code = PublicReferenceRetriever.retrieve.__code__
                retrieve_kwdefaults = dict(
                    PublicReferenceRetriever.retrieve.__kwdefaults__ or {}
                )
                retrieve_annotations = dict(PublicReferenceRetriever.retrieve.__annotations__)
                variant_field_name = ReferenceBundle.__dataclass_fields__["variant_id"].name
                assert ReferenceBundle.__init__.__closure__ is not None
                bundle_init_cell = ReferenceBundle.__init__.__closure__[0]
                bundle_init_cell_value = bundle_init_cell.cell_contents
                with tempfile.TemporaryDirectory() as directory:
                    client = SourceClient(
                        _catalog(),
                        cache_root=directory,
                        transport=transport,
                    )
                    retriever = PublicReferenceRetriever(client, window_bp=10)
                    transport.variant = variant
                    transport.context = context
                    transport.retriever = retriever
                    catalog_before = retriever.client.catalog.manifest()
                    limits_before = retriever.limits
                    source_transport = retriever.client.transport

                    with self.assertRaisesRegex(
                        ValidationError,
                        "mutated invocation scope or retriever configuration",
                    ):
                        retriever.retrieve(variant, context)

                    self.assertEqual(len(transport.calls), 1)
                    self.assertEqual(variant.to_dict(), variant_before)
                    self.assertIs(variant.annotations, annotations_alias)
                    self.assertIs(
                        variant.annotations["nested"],
                        nested_annotations_alias,
                    )
                    self.assertEqual(context.to_dict(), context_before)
                    self.assertEqual(retriever.window_bp, 10)
                    self.assertIs(type(retriever), PublicReferenceRetriever)
                    self.assertIs(retriever.limits, limits_before)
                    self.assertEqual(
                        retriever.limits.max_features_per_variant,
                        MAX_REFERENCE_FEATURES,
                    )
                    self.assertEqual(retriever.client.timeout_seconds, 20.0)
                    self.assertIs(retriever.ensembl.client, retriever.client)
                    self.assertIs(retriever.client.transport, source_transport)
                    self.assertEqual(retriever.client.catalog.manifest(), catalog_before)
                    self.assertEqual(
                        frozenset(retriever.client._limiters),
                        frozenset(item.source_id for item in retriever.client.catalog.list()),
                    )
                    self.assertEqual(EnsemblRestClient.source_id, "SRC-ENSEMBL-REST")
                    self.assertIs(data_sources_module.EnsemblRestClient, EnsemblRestClient)
                    self.assertIs(source_scope.__dict__, source_scope_dict)
                    self.assertIs(source_scope.__wrapped__, source_scope_wrapped)
                    self.assertIs(source_scope_wrapped.__code__, source_scope_wrapped_code)
                    self.assertIs(callback_isolation_module.ValidationError, isolation_error_type)
                    self.assertEqual(UcscRestClient._assemblies["GRCh38"], "hg38")
                    self.assertIs(PublicReferenceRetriever.retrieve.__code__, retrieve_code)
                    self.assertEqual(
                        PublicReferenceRetriever.retrieve.__kwdefaults__,
                        retrieve_kwdefaults,
                    )
                    self.assertEqual(
                        PublicReferenceRetriever.retrieve.__annotations__,
                        retrieve_annotations,
                    )
                    self.assertEqual(
                        ReferenceBundle.__dataclass_fields__["variant_id"].name,
                        variant_field_name,
                    )
                    self.assertIs(bundle_init_cell.cell_contents, bundle_init_cell_value)
                    self.assertTrue(
                        all(
                            limiter._next_allowed < 10**100
                            for limiter in retriever.client._limiters.values()
                        )
                    )

                    clean = retriever.retrieve(variant, context)
                    self.assertEqual(clean.variant_id, variant_before["variant_id"])
                    self.assertEqual(clean.context_key, context.key)
                    self.assertEqual(len(transport.calls), 3)

    def test_reference_callback_cannot_shadow_semantic_restore_builtins(self) -> None:
        class ShadowingTransport(FakeTransport):
            def __init__(self, responses: dict[str, object], poisoned_name: str) -> None:
                super().__init__(responses)
                self.mutate_once = True
                self.poisoned_name = poisoned_name

            def request(self, method, url, headers, timeout_seconds):
                if self.mutate_once:
                    self.mutate_once = False
                    vars(data_sources_module)[self.poisoned_name] = None
                return super().request(method, url, headers, timeout_seconds)

        manifest = fixture_manifest()
        variant = manifest.variants[0]
        query_start = variant.start - 10
        query_end = variant.end + 10
        sequence_url = (
            "https://ucsc.example/getData/sequence?chrom=chr7"
            f"&end={query_end}&genome=hg38&start={query_start - 1}"
        )
        overlap_url = (
            "https://ensembl.example/overlap/region/homo_sapiens/"
            f"7:{query_start}-{query_end}?feature=gene&feature=motif&feature=regulatory"
        )
        responses = {
            sequence_url: {"dna": "A" * (query_end - query_start + 1)},
            overlap_url: [],
        }
        namespace = vars(data_sources_module)
        missing = object()
        poisoned_names = (
            "dict",
            "Exception",
            "BaseException",
            "globals",
            "type",
            "vars",
            "cast",
            "detached_callback_guard",
            "_restore_mutable_container_configuration",
        )

        for poisoned_name in poisoned_names:
            with self.subTest(poisoned_name=poisoned_name):
                original = namespace.get(poisoned_name, missing)
                transport = ShadowingTransport(responses, poisoned_name)
                try:
                    with tempfile.TemporaryDirectory() as directory:
                        retriever = PublicReferenceRetriever(
                            SourceClient(
                                _catalog(),
                                cache_root=directory,
                                transport=transport,
                            ),
                            window_bp=10,
                        )
                        with self.assertRaisesRegex(
                            ValidationError,
                            "mutated invocation scope or retriever configuration",
                        ):
                            retriever.retrieve(variant, manifest.context)
                        if original is missing:
                            self.assertNotIn(poisoned_name, namespace)
                        else:
                            self.assertIs(namespace[poisoned_name], original)

                        clean = retriever.retrieve(variant, manifest.context)
                        self.assertEqual(clean.variant_id, variant.variant_id)
                        self.assertEqual(clean.context_key, manifest.context.key)
                finally:
                    if original is missing:
                        namespace.pop(poisoned_name, None)
                    else:
                        namespace[poisoned_name] = original

    def test_raising_reference_callback_cannot_poison_exception_dispatch(self) -> None:
        class RaisingShadowTransport(FakeTransport):
            def __init__(self, responses: dict[str, object]) -> None:
                super().__init__(responses)
                self.mutate_once = True

            def request(self, method, url, headers, timeout_seconds):
                if self.mutate_once:
                    self.mutate_once = False
                    vars(data_sources_module)["Exception"] = None
                    raise RuntimeError("transport failed after shadowing exception dispatch")
                return super().request(method, url, headers, timeout_seconds)

        manifest = fixture_manifest()
        variant = manifest.variants[0]
        query_start = variant.start - 10
        query_end = variant.end + 10
        sequence_url = (
            "https://ucsc.example/getData/sequence?chrom=chr7"
            f"&end={query_end}&genome=hg38&start={query_start - 1}"
        )
        overlap_url = (
            "https://ensembl.example/overlap/region/homo_sapiens/"
            f"7:{query_start}-{query_end}?feature=gene&feature=motif&feature=regulatory"
        )
        transport = RaisingShadowTransport(
            {
                sequence_url: {"dna": "A" * (query_end - query_start + 1)},
                overlap_url: [],
            }
        )
        try:
            with tempfile.TemporaryDirectory() as directory:
                retriever = PublicReferenceRetriever(
                    SourceClient(_catalog(), cache_root=directory, transport=transport),
                    window_bp=10,
                )
                with self.assertRaisesRegex(
                    ValidationError,
                    "mutated invocation scope or retriever configuration",
                ):
                    retriever.retrieve(variant, manifest.context)
                self.assertNotIn("Exception", vars(data_sources_module))

                clean = retriever.retrieve(variant, manifest.context)
                self.assertEqual(clean.variant_id, variant.variant_id)
                self.assertEqual(clean.context_key, manifest.context.key)
        finally:
            vars(data_sources_module).pop("Exception", None)

    def test_external_integrity_guard_cannot_poison_derivation_before_source_work(
        self,
    ) -> None:
        class DynamicTransport:
            def __init__(self) -> None:
                self.calls: list[str] = []

            def request(self, method, url, headers, timeout_seconds):
                del method, headers, timeout_seconds
                self.calls.append(url)
                if "/getData/sequence" in url:
                    query = parse_qs(urlsplit(url).query)
                    length = int(query["end"][0]) - int(query["start"][0])
                    body = json.dumps({"dna": "A" * length}).encode("utf-8")
                else:
                    body = b"[]"
                return TransportResponse(
                    200,
                    url,
                    {"content-type": "application/json"},
                    body,
                    0.001,
                )

        manifest = fixture_manifest()
        variant = manifest.variants[0]
        context = manifest.context
        transport = DynamicTransport()
        original_variant_interval = data_sources_module.variant_interval
        poisoned_derivation_calls: list[str] = []
        guard_calls = 0

        def poisoned_variant_interval(selected_variant):
            poisoned_derivation_calls.append(selected_variant.variant_id)
            return original_variant_interval(selected_variant)

        def mutating_external_guard() -> None:
            nonlocal guard_calls
            guard_calls += 1
            if guard_calls == 1:
                data_sources_module.variant_interval = poisoned_variant_interval

        with tempfile.TemporaryDirectory() as directory:
            retriever = PublicReferenceRetriever(
                SourceClient(
                    _catalog(),
                    cache_root=directory,
                    transport=transport,
                ),
                window_bp=10,
            )

            with self.assertRaisesRegex(
                ValidationError,
                "mutated invocation scope or retriever configuration",
            ):
                retriever.retrieve(
                    variant,
                    context,
                    _external_integrity_guard=mutating_external_guard,
                )

            self.assertEqual(guard_calls, 1)
            self.assertEqual(poisoned_derivation_calls, [])
            self.assertEqual(transport.calls, [])
            self.assertIs(data_sources_module.variant_interval, original_variant_interval)

            clean = retriever.retrieve(variant, context)
            self.assertEqual(clean.variant_id, variant.variant_id)
            self.assertEqual(len(transport.calls), 2)

    def test_enrichment_callback_manifest_mutation_is_atomic_and_retryable(self) -> None:
        class ManifestMutatingTransport:
            def __init__(self, manifest, *, raise_after_mutation: bool) -> None:
                self.manifest = manifest
                self.raise_after_mutation = raise_after_mutation
                self.mutate_once = True
                self.calls: list[str] = []

            def request(self, method, url, headers, timeout_seconds):
                del method, headers, timeout_seconds
                self.calls.append(url)
                if self.mutate_once:
                    self.mutate_once = False
                    dict.__setitem__(
                        self.manifest.metadata,
                        "base-dict-bypass",
                        True,
                    )
                    list.append(
                        self.manifest.candidate_elements[0].annotations[
                            "alternative_explanations"
                        ],
                        "base-list-bypass",
                    )
                    object.__setattr__(self.manifest, "case_id", "redirected-case")
                    object.__setattr__(self.manifest.context, "cell_state", "redirected-state")
                    object.__setattr__(
                        self.manifest.variants[1],
                        "variant_id",
                        "redirected-second-variant",
                    )
                    object.__setattr__(
                        self.manifest.candidate_elements[0],
                        "element_id",
                        "redirected-element",
                    )
                    if self.raise_after_mutation:
                        raise SourceError("manifest mutation transport failure")
                if "/getData/sequence" in url:
                    query = parse_qs(urlsplit(url).query)
                    length = int(query["end"][0]) - int(query["start"][0])
                    body = json.dumps({"dna": "A" * length}).encode("utf-8")
                else:
                    body = b"[]"
                return TransportResponse(
                    200,
                    url,
                    {"content-type": "application/json"},
                    body,
                    0.001,
                )

        for raise_after_mutation in (False, True):
            with self.subTest(raise_after_mutation=raise_after_mutation):
                base_manifest = fixture_manifest()
                second_variant = replace(
                    base_manifest.variants[0],
                    variant_id="variant-manifest-mutation-2",
                    start=base_manifest.variants[0].start + 10,
                    end=base_manifest.variants[0].end + 10,
                )
                manifest = replace(
                    base_manifest,
                    variants=(base_manifest.variants[0], second_variant),
                )
                manifest_before = copy.deepcopy(manifest.to_dict())
                context_alias = manifest.context
                second_variant_alias = manifest.variants[1]
                element_alias = manifest.candidate_elements[0]
                metadata_alias = manifest.metadata
                element_annotations_alias = element_alias.annotations
                alternative_explanations_alias = element_alias.annotations[
                    "alternative_explanations"
                ]
                context_before = copy.deepcopy(context_alias.to_dict())
                second_variant_before = copy.deepcopy(second_variant_alias.to_dict())
                element_before = copy.deepcopy(element_alias.to_dict())
                transport = ManifestMutatingTransport(
                    manifest,
                    raise_after_mutation=raise_after_mutation,
                )
                with tempfile.TemporaryDirectory() as directory:
                    retriever = PublicReferenceRetriever(
                        SourceClient(
                            _catalog(),
                            cache_root=directory,
                            transport=transport,
                        ),
                        window_bp=10,
                    )
                    with self.assertRaisesRegex(
                        ValidationError,
                        "mutated enrichment manifest scope",
                    ):
                        retriever.enrich_manifest(manifest)

                    self.assertEqual(len(transport.calls), 1)
                    self.assertEqual(manifest.to_dict(), manifest_before)
                    self.assertIs(manifest.metadata, metadata_alias)
                    self.assertEqual(context_alias.to_dict(), context_before)
                    self.assertEqual(second_variant_alias.to_dict(), second_variant_before)
                    self.assertEqual(element_alias.to_dict(), element_before)
                    self.assertIs(
                        element_alias.annotations,
                        element_annotations_alias,
                    )
                    self.assertIs(
                        element_alias.annotations["alternative_explanations"],
                        alternative_explanations_alias,
                    )

                    clean = retriever.enrich_manifest(manifest)
                    self.assertEqual(clean.manifest.case_id, manifest_before["case_id"])
                    self.assertEqual(
                        tuple(item.variant_id for item in clean.bundles),
                        tuple(item["variant_id"] for item in manifest_before["variants"]),
                    )
                    self.assertEqual(len(transport.calls), 5)

    def test_nested_cross_retriever_callback_fails_before_poisoned_snapshot(self) -> None:
        class DynamicTransport:
            def __init__(self) -> None:
                self.calls: list[str] = []

            def request(self, method, url, headers, timeout_seconds):
                del method, headers, timeout_seconds
                self.calls.append(url)
                if "/getData/sequence" in url:
                    query = parse_qs(urlsplit(url).query)
                    length = int(query["end"][0]) - int(query["start"][0])
                    body = json.dumps({"dna": "A" * length}).encode("utf-8")
                else:
                    body = b"[]"
                return TransportResponse(
                    200,
                    url,
                    {"content-type": "application/json"},
                    body,
                    0.001,
                )

        class NestedTransport(DynamicTransport):
            def __init__(self) -> None:
                super().__init__()
                self.trigger_once = True
                self.other = None
                self.variant = None
                self.context = None
                self.nested_error: ValidationError | None = None

            def request(self, method, url, headers, timeout_seconds):
                if self.trigger_once:
                    self.trigger_once = False
                    assert self.other is not None
                    assert self.variant is not None
                    assert self.context is not None
                    visible_state = getattr(
                        data_sources_module,
                        "_PUBLIC_REFERENCE_CALLBACK_STATE",
                        None,
                    )
                    if visible_state is not None:
                        vars(visible_state).clear()
                    EnsemblRestClient.source_id = "SRC-NESTED-POISON"
                    try:
                        self.other.retrieve(self.variant, self.context)
                    except ValidationError as exc:
                        self.nested_error = exc
                return super().request(method, url, headers, timeout_seconds)

        manifest = fixture_manifest()
        variant = manifest.variants[0]
        context = manifest.context
        outer_transport = NestedTransport()
        inner_transport = DynamicTransport()
        self.assertFalse(
            hasattr(data_sources_module, "_PUBLIC_REFERENCE_CALLBACK_STATE")
        )
        with (
            tempfile.TemporaryDirectory() as outer_directory,
            tempfile.TemporaryDirectory() as inner_directory,
        ):
            outer = PublicReferenceRetriever(
                SourceClient(
                    _catalog(),
                    cache_root=outer_directory,
                    transport=outer_transport,
                ),
                window_bp=10,
            )
            inner = PublicReferenceRetriever(
                SourceClient(
                    _catalog(),
                    cache_root=inner_directory,
                    transport=inner_transport,
                ),
                window_bp=10,
            )
            outer_transport.other = inner
            outer_transport.variant = variant
            outer_transport.context = context

            with self.assertRaisesRegex(
                ValidationError,
                "mutated invocation scope or retriever configuration",
            ):
                outer.retrieve(variant, context)

            self.assertEqual(len(outer_transport.calls), 1)
            self.assertEqual(inner_transport.calls, [])
            self.assertIsNotNone(outer_transport.nested_error)
            self.assertIn("nested public reference retrieval", str(outer_transport.nested_error))
            self.assertEqual(EnsemblRestClient.source_id, "SRC-ENSEMBL-REST")

            self.assertEqual(outer.retrieve(variant, context).variant_id, variant.variant_id)
            self.assertEqual(inner.retrieve(variant, context).variant_id, variant.variant_id)
            self.assertEqual(len(outer_transport.calls), 3)
            self.assertEqual(len(inner_transport.calls), 2)

    def test_source_scope_alias_substitution_fails_before_transport(self) -> None:
        manifest = fixture_manifest()
        transport = SequenceTransport([])
        with tempfile.TemporaryDirectory() as directory:
            retriever = PublicReferenceRetriever(
                SourceClient(
                    _catalog(),
                    cache_root=directory,
                    transport=transport,
                )
            )
            cases = (
                (
                    "source_callback_scope",
                    lambda: retriever.retrieve(
                        manifest.variants[0],
                        manifest.context,
                    ),
                ),
                (
                    "source_manifest_callback_scope",
                    lambda: retriever.enrich_manifest(manifest),
                ),
            )
            for attribute, operation in cases:
                with (
                    self.subTest(attribute=attribute),
                    patch.object(data_sources_module, attribute, object()),
                    self.assertRaisesRegex(ValidationError, "callback scope is invalid"),
                ):
                    operation()

        self.assertEqual(transport.calls, [])

    def test_failed_source_request_carries_a_non_negative_failure_receipt(self) -> None:
        catalog = _catalog()
        transport = FakeTransport({})
        with tempfile.TemporaryDirectory() as directory:
            client = SourceClient(catalog, cache_root=directory, transport=transport)
            with self.assertRaises(SourceError) as captured:
                client.fetch_json("SRC-ENSEMBL-REST", "/missing")
            receipt = captured.exception.receipt
            self.assertIsNotNone(receipt)
            self.assertEqual(receipt.status.value, "failed")
            self.assertIn("not a negative", receipt.warnings[0])

    def test_request_paths_and_redirects_cannot_escape_the_source_origin(self) -> None:
        source = _source()
        redirected = _response(200, "https://metadata.example/secret")
        with tempfile.TemporaryDirectory() as directory:
            transport = SequenceTransport([redirected])
            client = SourceClient(
                SourceCatalog((source,)),
                cache_root=directory,
                transport=transport,
                retry_policy=RetryPolicy(attempts=3, initial_backoff_seconds=0),
            )
            self.assertEqual(
                client.build_url(source, "/canonical", {"z": 2, "a": 1}),
                client.build_url(source, "/canonical", {"a": 1, "z": 2}),
            )
            with self.assertRaisesRegex(ValidationError, "relative path"):
                client.build_url(source, "//metadata.example/secret")
            with self.assertRaises(SourceError) as captured:
                client.fetch_json(source.source_id, "/lookup")

            self.assertEqual(len(transport.calls), 1)
            self.assertEqual(captured.exception.receipt.attempts, 1)
            self.assertIn("redirected outside", captured.exception.receipt.error_message)
            self.assertEqual(list(Path(directory).glob("*.json")), [])

    def test_invalid_json_is_neither_retried_nor_cached(self) -> None:
        source = _source()
        url = "https://ensembl.example/invalid"
        invalid_bodies = (
            b'{"score":NaN}',
            b'{"id":1,"id":2}',
            b'{"description":"\\ud800"}',
        )
        for body in invalid_bodies:
            with self.subTest(body=body), tempfile.TemporaryDirectory() as directory:
                transport = SequenceTransport([_response(200, url, body)])
                client = SourceClient(
                    SourceCatalog((source,)),
                    cache_root=directory,
                    transport=transport,
                    retry_policy=RetryPolicy(attempts=3, initial_backoff_seconds=0),
                )
                with self.assertRaisesRegex(SourceError, "failed after 1 attempts") as captured:
                    client.fetch_json(source.source_id, "/invalid")

                self.assertEqual(len(transport.calls), 1)
                self.assertEqual(captured.exception.receipt.attempts, 1)
                self.assertEqual(list(Path(directory).glob("*.json")), [])

    def test_invalid_text_and_not_found_metadata_are_classified_source_failures(self) -> None:
        source = _source()
        url = "https://ensembl.example/metadata"
        oversized_content_type = "x" * 257
        cases = (
            (200, False, b"bounded text"),
            (404, True, b""),
        )
        for status, allow_not_found, body in cases:
            with self.subTest(status=status), tempfile.TemporaryDirectory() as directory:
                response = TransportResponse(
                    status,
                    url,
                    {"content-type": oversized_content_type},
                    body,
                    0.001,
                )
                transport = SequenceTransport([response])
                client = SourceClient(
                    SourceCatalog((source,)),
                    cache_root=directory,
                    transport=transport,
                    retry_policy=RetryPolicy(attempts=3, initial_backoff_seconds=0),
                )

                with self.assertRaisesRegex(
                    SourceError,
                    "failed after 1 attempts",
                ) as captured:
                    client.fetch_text(
                        source.source_id,
                        "/metadata",
                        allow_not_found=allow_not_found,
                        cache=False,
                    )

                self.assertEqual(captured.exception.receipt.status, FetchStatus.FAILED)
                self.assertEqual(captured.exception.receipt.attempts, 1)
                self.assertEqual(captured.exception.receipt.http_status, status)
                self.assertEqual(len(transport.calls), 1)
                self.assertEqual(list(Path(directory).glob("*.json")), [])

    def test_only_declared_retry_statuses_are_retried(self) -> None:
        source = _source()
        url = "https://ensembl.example/status"
        retry_policy = RetryPolicy(
            attempts=3,
            initial_backoff_seconds=0,
            maximum_backoff_seconds=0,
        )
        with tempfile.TemporaryDirectory() as directory:
            bad_request = SequenceTransport([_response(400, url)])
            client = SourceClient(
                SourceCatalog((source,)),
                cache_root=directory,
                transport=bad_request,
                retry_policy=retry_policy,
            )
            with self.assertRaises(SourceError) as captured:
                client.fetch_json(source.source_id, "/status", cache=False)
            self.assertEqual(len(bad_request.calls), 1)
            self.assertEqual(captured.exception.receipt.attempts, 1)

        with tempfile.TemporaryDirectory() as directory:
            temporary_failure = SequenceTransport(
                [_response(503, url), _response(200, url, b'{"ok":true}')]
            )
            client = SourceClient(
                SourceCatalog((source,)),
                cache_root=directory,
                transport=temporary_failure,
                retry_policy=retry_policy,
            )
            payload = client.fetch_json(source.source_id, "/status", cache=False)
            self.assertEqual(payload.value, {"ok": True})
            self.assertEqual(payload.receipt.attempts, 2)
            self.assertEqual(len(temporary_failure.calls), 2)

    def test_not_found_has_a_receipt_and_is_not_retried(self) -> None:
        source = _source()
        url = "https://ensembl.example/missing"
        retry_policy = RetryPolicy(attempts=3, initial_backoff_seconds=0)
        with tempfile.TemporaryDirectory() as directory:
            transport = SequenceTransport([_response(404, url)])
            client = SourceClient(
                SourceCatalog((source,)),
                cache_root=directory,
                transport=transport,
                retry_policy=retry_policy,
            )
            with self.assertRaises(SourceNotFoundError) as captured:
                client.fetch_json(source.source_id, "/missing")
            self.assertEqual(captured.exception.receipt.status, FetchStatus.NOT_FOUND)
            self.assertEqual(captured.exception.receipt.attempts, 1)
            self.assertEqual(len(transport.calls), 1)

    def test_http_rate_limit_is_retried_then_reported_distinctly(self) -> None:
        source = _source()
        url = "https://ensembl.example/limited"
        transport = SequenceTransport([_response(429, url), _response(429, url)])
        with tempfile.TemporaryDirectory() as directory:
            client = SourceClient(
                SourceCatalog((source,)),
                cache_root=directory,
                transport=transport,
                retry_policy=RetryPolicy(
                    attempts=2,
                    initial_backoff_seconds=0,
                    maximum_backoff_seconds=0,
                ),
            )
            with self.assertRaises(SourceRateLimitError) as captured:
                client.fetch_json(source.source_id, "/limited", cache=False)

            self.assertEqual(captured.exception.receipt.status, FetchStatus.RATE_LIMITED)
            self.assertEqual(captured.exception.receipt.attempts, 2)
            self.assertEqual(len(transport.calls), 2)

    def test_corrupted_cache_entry_is_replaced_by_a_fresh_response(self) -> None:
        source = _source()
        url = "https://ensembl.example/cached"
        transport = FakeTransport({url: {"id": "ENSG000001"}})
        with tempfile.TemporaryDirectory() as directory:
            client = SourceClient(
                SourceCatalog((source,)),
                cache_root=directory,
                transport=transport,
            )
            client.fetch_json(source.source_id, "/cached")
            cache_path = next(Path(directory).glob("*.json"))
            raw = json.loads(cache_path.read_text(encoding="utf-8"))
            corrupted = copy.deepcopy(raw)
            corrupted["source_id"] = "SRC-OTHER"
            cache_path.write_text(json.dumps(corrupted), encoding="utf-8")

            refreshed = client.fetch_json(source.source_id, "/cached")

            self.assertEqual(refreshed.receipt.status, FetchStatus.FETCHED)
            self.assertEqual(len(transport.calls), 2)
            repaired = json.loads(cache_path.read_text(encoding="utf-8"))
            self.assertEqual(repaired["source_id"], source.source_id)

    def test_concurrent_cache_writes_leave_one_verified_entry(self) -> None:
        source = _source()
        request_hash = content_hash({"request": "same"})
        url = "https://ensembl.example/concurrent"
        body = b'{"ok":true}'
        with tempfile.TemporaryDirectory() as directory:
            cache = SourceCache(directory)

            def write(_: int) -> None:
                cache.put(
                    request_hash=request_hash,
                    source=source,
                    url=url,
                    body=body,
                    content_type="application/json",
                    ttl_seconds=60,
                )

            with ThreadPoolExecutor(max_workers=8) as pool:
                tuple(pool.map(write, range(32)))

            loaded = cache.get(request_hash, source=source, max_response_bytes=1_024)
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.body, body)
            self.assertEqual(len(list(Path(directory).glob("*.tmp"))), 0)

    def test_numeric_and_iterable_configuration_is_exact_and_bounded(self) -> None:
        invalid_specs = (
            {"rate_limit_per_minute": True},
            {"max_response_bytes": math.inf},
            {"enabled": 1},
            {"base_url": "https://user:secret@ensembl.example"},
        )
        for overrides in invalid_specs:
            with self.subTest(overrides=overrides), self.assertRaises(ValidationError):
                _source(**overrides)
        for policy in (
            {"attempts": True},
            {"initial_backoff_seconds": math.nan},
            {"retry_statuses": (503, 503)},
        ):
            with self.subTest(policy=policy), self.assertRaises(ValidationError):
                RetryPolicy(**policy)  # type: ignore[arg-type]
        with self.assertRaises(ValidationError):
            SourceClient(_catalog(), timeout_seconds=math.nan)
        with self.assertRaises(ValidationError):
            SourceClient(_catalog(), timeout_seconds=10**400)
        with self.assertRaises(ValidationError):
            PublicReferenceRetriever(window_bp=True)
        with self.assertRaises(ValidationError):
            PublicReferenceRetriever(
                window_bp=11,
                limits=ReferenceRetrievalLimits(max_window_bp=10),
            )
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValidationError, "between 1 and 32"):
                EnsemblRestClient(
                    SourceClient(_catalog(), cache_root=directory)
                ).overlap_region(
                    "7",
                    1,
                    10,
                    features=repeat("gene"),
                )

    def test_oversized_response_fails_once_without_cache_write(self) -> None:
        source = _source(max_response_bytes=1_024)
        url = "https://ensembl.example/large"
        transport = SequenceTransport([_response(200, url, b"x" * 1_025)])
        with tempfile.TemporaryDirectory() as directory:
            client = SourceClient(
                SourceCatalog((source,)),
                cache_root=directory,
                transport=transport,
                retry_policy=RetryPolicy(attempts=3, initial_backoff_seconds=0),
            )
            with self.assertRaisesRegex(SourceError, "failed after 1 attempts") as captured:
                client.fetch_json(source.source_id, "/large")
            self.assertEqual(captured.exception.receipt.attempts, 1)
            self.assertEqual(len(transport.calls), 1)
            self.assertEqual(list(Path(directory).glob("*.json")), [])

    def test_candidate_elements_are_canonical_and_conflicts_fail_closed(self) -> None:
        manifest = fixture_manifest()
        variant = manifest.variants[0]
        gene_a = {"feature_type": "gene", "id": "GENE-B", "external_name": "B"}
        gene_b = {"feature_type": "gene", "id": "GENE-A", "external_name": "A"}
        regulatory_a = {
            "feature_type": "regulatory",
            "id": "element-z",
            "seq_region_name": "7",
            "start": variant.start,
            "end": variant.end,
        }
        regulatory_b = {
            "feature_type": "motif",
            "id": "element-a",
            "seq_region_name": "7",
            "start": variant.start,
            "end": variant.end,
        }
        forward = PublicReferenceRetriever._candidate_elements(
            (gene_a, regulatory_a, gene_b, regulatory_b),
            manifest.context,
            variant,
        )
        reverse = PublicReferenceRetriever._candidate_elements(
            (regulatory_b, gene_b, regulatory_a, gene_a),
            manifest.context,
            variant,
        )
        self.assertEqual(
            [item.to_dict() for item in forward],
            [item.to_dict() for item in reverse],
        )
        self.assertEqual([item.element_id for item in forward], ["element-a", "element-z"])
        self.assertTrue(all(item.target_genes == ("A", "B") for item in forward))

        conflict = dict(regulatory_a) | {"end": variant.end + 1}
        with self.assertRaisesRegex(ValidationError, "conflicting features"):
            PublicReferenceRetriever._candidate_elements(
                (gene_a, regulatory_a, conflict),
                manifest.context,
                variant,
            )

    def test_malformed_overlap_response_is_an_explicit_abstention(self) -> None:
        catalog = _catalog()
        manifest = fixture_manifest()
        variant = manifest.variants[0]
        query_start = variant.start - 10
        query_end = variant.end + 10
        sequence_url = (
            "https://ucsc.example/getData/sequence?chrom=chr7"
            f"&end={query_end}&genome=hg38&start={query_start - 1}"
        )
        overlap_url = (
            "https://ensembl.example/overlap/region/homo_sapiens/"
            f"7:{query_start}-{query_end}?feature=gene&feature=motif&feature=regulatory"
        )
        transport = FakeTransport(
            {
                sequence_url: {"dna": "A" * (query_end - query_start + 1)},
                overlap_url: {"unexpected": "object"},
            }
        )
        with tempfile.TemporaryDirectory() as directory:
            retriever = PublicReferenceRetriever(
                SourceClient(catalog, cache_root=directory, transport=transport),
                window_bp=10,
            )
            bundle = retriever.retrieve(variant, manifest.context)

            self.assertIsNotNone(bundle.sequence)
            self.assertEqual(bundle.elements, ())
            self.assertEqual(len(bundle.receipts), 2)
            self.assertIn("overlap response was not an array", bundle.warnings[0])

    def test_json_payloads_are_recursively_immutable(self) -> None:
        source = _source()
        url = "https://ensembl.example/immutable"
        transport = FakeTransport({url: {"rows": [{"id": 1}]}})
        with tempfile.TemporaryDirectory() as directory:
            payload = SourceClient(
                SourceCatalog((source,)),
                cache_root=directory,
                transport=transport,
            ).fetch_json(source.source_id, "/immutable")

            with self.assertRaises(TypeError):
                payload.value["rows"][0]["id"] = 2

    def test_receipt_sequence_and_bundle_provenance_is_closed(self) -> None:
        context = fixture_manifest().context
        request_hash = content_hash({"request": "sequence"})
        response_hash = content_hash({"response": "ACGT"})
        receipt = FetchReceipt(
            source_id="SRC-UCSC-REST",
            source_version="fixture-1",
            url="https://ucsc.example/sequence",
            request_hash=request_hash,
            response_hash=response_hash,
            status=FetchStatus.FETCHED,
            http_status=200,
            attempts=1,
            retrieved_at="2026-08-20T00:00:00+00:00",
            elapsed_seconds=0.01,
            cache_expires_at=None,
        )
        for field_name, malformed in (
            ("request_hash", "sha256:not-a-digest"),
            ("response_hash", "sha256:not-a-digest"),
            ("attempts", True),
            ("retrieved_at", "2026-08-20T00:00:00"),
            ("http_status", 404),
        ):
            with self.subTest(field_name=field_name), self.assertRaises(ValidationError):
                replace(receipt, **{field_name: malformed})

        with self.assertRaisesRegex(ValidationError, "does not match its receipt"):
            SequenceSlice(
                "GRCh38",
                "chr7",
                100,
                103,
                "ACGT",
                "SRC-OTHER",
                receipt,
            )
        sequence = SequenceSlice(
            "GRCh38",
            "chr7",
            100,
            103,
            "ACGT",
            receipt.source_id,
            receipt,
        )
        feature = {"feature_type": "gene", "id": "GENE_A", "nested": [1]}
        bundle = ReferenceBundle.create(
            variant_id="v1",
            context=context,
            sequence=sequence,
            elements=(),
            raw_features=(feature,),
            receipts=(receipt,),
            warnings=(),
        )
        feature["nested"].append(2)
        self.assertEqual(bundle.raw_features[0]["nested"], [1])
        self.assertEqual(FetchReceipt.from_dict(receipt.to_dict()), receipt)
        self.assertEqual(SequenceSlice.from_dict(sequence.to_dict()), sequence)
        self.assertEqual(
            ReferenceBundle.from_dict(bundle.to_dict(), context),
            bundle,
        )
        with self.assertRaisesRegex(ValidationError, "does not match its payload"):
            replace(bundle, content_address="sha256:" + "0" * 64)

        malformed_sequence = copy.deepcopy(bundle.to_dict())
        malformed_sequence["sequence"]["sequence"] = "ACGX"
        malformed_receipt = copy.deepcopy(bundle.to_dict())
        malformed_receipt["receipts"][0]["url"] = "file:///not-public"
        duplicate_features = copy.deepcopy(bundle.to_dict())
        duplicate_features["raw_features"] *= 2
        duplicate_features["content_address"] = content_hash(
            {
                key: value
                for key, value in duplicate_features.items()
                if key != "content_address"
            }
        )
        for malformed in (malformed_sequence, malformed_receipt, duplicate_features):
            with self.subTest(malformed=malformed), self.assertRaises(ValidationError):
                ReferenceBundle.from_dict(malformed, context)

    def test_persisted_source_types_reject_non_utf8_text(self) -> None:
        with self.assertRaisesRegex(ValidationError, "valid UTF-8"):
            _source(terms="terms\ud800")

        context = fixture_manifest().context
        receipt = FetchReceipt(
            source_id="SRC-UCSC-REST",
            source_version="fixture-1",
            url="https://ucsc.example/sequence",
            request_hash=content_hash({"request": "sequence"}),
            response_hash=content_hash({"response": "ACGT"}),
            status=FetchStatus.FETCHED,
            http_status=200,
            attempts=1,
            retrieved_at="2026-08-20T00:00:00+00:00",
            elapsed_seconds=0.01,
            cache_expires_at=None,
        )
        sequence = SequenceSlice(
            assembly="GRCh38",
            chromosome="chr7",
            start=100,
            end=103,
            sequence="ACGT",
            source_id=receipt.source_id,
            receipt=receipt,
        )
        bundle = ReferenceBundle.create(
            variant_id="v1",
            context=context,
            sequence=sequence,
            elements=(),
            raw_features=(),
            receipts=(receipt,),
            warnings=(),
        )

        malformed_receipt = receipt.to_dict()
        malformed_receipt["source_version"] = "fixture-\ud800"
        with self.assertRaisesRegex(ValidationError, "valid UTF-8"):
            FetchReceipt.from_dict(malformed_receipt)

        malformed_sequence = sequence.to_dict()
        malformed_sequence["assembly"] = "GRCh38\ud800"
        with self.assertRaisesRegex(ValidationError, "valid UTF-8"):
            SequenceSlice.from_dict(malformed_sequence)

        malformed_bundle = bundle.to_dict()
        malformed_bundle["warnings"] = ["warning\ud800"]
        with self.assertRaisesRegex(ValidationError, "valid UTF-8"):
            ReferenceBundle.from_dict(malformed_bundle, context)

        malformed_bundle = bundle.to_dict()
        malformed_bundle["raw_features"] = [
            {"nested": {"description": "invalid\ud800"}}
        ]
        with self.assertRaisesRegex(ValidationError, "valid UTF-8"):
            ReferenceBundle.from_dict(malformed_bundle, context)

    def test_empty_bundle_rehydration_requires_the_exact_supplied_context(self) -> None:
        context = fixture_manifest().context
        bundle = ReferenceBundle.create(
            variant_id="v1",
            context=context,
            sequence=None,
            elements=(),
            raw_features=(),
            receipts=(),
            warnings=(),
        )
        malformed = bundle.to_dict()
        malformed["context_key"] = "GRCh37|glioma|adult|stem_like|unspecified|untreated"
        malformed["content_address"] = content_hash(
            {key: value for key, value in malformed.items() if key != "content_address"}
        )

        with self.assertRaisesRegex(ValidationError, "does not match the supplied context"):
            ReferenceBundle.from_dict(malformed, context)

        same_key_contexts = (
            replace(context, source_version=f"{context.source_version}-substituted"),
            replace(context, assay_support=context.assay_support + ("single-cell-atac",)),
        )
        for substituted in same_key_contexts:
            with self.subTest(substituted=substituted):
                self.assertEqual(substituted.key, context.key)
                substituted_bundle = ReferenceBundle.create(
                    variant_id="v1",
                    context=substituted,
                    sequence=None,
                    elements=(),
                    raw_features=(),
                    receipts=(),
                    warnings=(),
                )
                self.assertNotEqual(
                    substituted_bundle.context_address,
                    bundle.context_address,
                )
                self.assertNotEqual(
                    substituted_bundle.content_address,
                    bundle.content_address,
                )
                with self.assertRaisesRegex(
                    ValidationError,
                    "context_address does not match the supplied context",
                ):
                    ReferenceBundle.from_dict(bundle.to_dict(), substituted)

        delimiter_left = replace(
            context,
            disease_class="diffuse|glioma",
            age_group="adult",
        )
        delimiter_right = replace(
            context,
            disease_class="diffuse",
            age_group="glioma|adult",
        )
        self.assertEqual(delimiter_left.key, delimiter_right.key)
        left_bundle = ReferenceBundle.create(
            variant_id="v1",
            context=delimiter_left,
            sequence=None,
            elements=(),
            raw_features=(),
            receipts=(),
            warnings=(),
        )
        right_bundle = ReferenceBundle.create(
            variant_id="v1",
            context=delimiter_right,
            sequence=None,
            elements=(),
            raw_features=(),
            receipts=(),
            warnings=(),
        )
        self.assertNotEqual(left_bundle.context_address, right_bundle.context_address)
        with self.assertRaisesRegex(ValidationError, "context_address"):
            ReferenceBundle.from_dict(left_bundle.to_dict(), delimiter_right)

        altered_address = bundle.to_dict()
        altered_address["context_address"] = "sha256:" + "0" * 64
        altered_address["content_address"] = content_hash(
            {
                key: value
                for key, value in altered_address.items()
                if key != "content_address"
            }
        )
        with self.assertRaisesRegex(ValidationError, "context_address"):
            ReferenceBundle.from_dict(altered_address, context)

    def test_reference_context_and_canonical_json_failures_are_normalized(self) -> None:
        context = fixture_manifest().context
        context_raw = context.to_dict()
        with patch(
            "glio_noncode.data_sources.ReferenceContext.to_dict",
            side_effect=(context_raw, RuntimeError("unsafe raw traversal detail")),
        ), self.assertRaisesRegex(ValidationError, "context is malformed") as raised:
            ReferenceBundle.create(
                variant_id="v1",
                context=context,
                sequence=None,
                elements=(),
                raw_features=(),
                receipts=(),
                warnings=(),
            )
        self.assertNotIn("unsafe raw traversal detail", str(raised.exception))

        with patch(
            "glio_noncode.data_sources.canonical_bytes",
            side_effect=TypeError("unsafe canonical conversion detail"),
        ), self.assertRaisesRegex(ValidationError, "canonical JSON") as raised:
            ReferenceBundle.create(
                variant_id="v1",
                context=context,
                sequence=None,
                elements=(),
                raw_features=(),
                receipts=(),
                warnings=(),
            )
        self.assertNotIn("unsafe canonical conversion detail", str(raised.exception))

        bundle = ReferenceBundle.create(
            variant_id="v1",
            context=context,
            sequence=None,
            elements=(),
            raw_features=(),
            receipts=(),
            warnings=(),
        )
        oversized_integer = bundle.to_dict()
        oversized_integer["raw_features"] = [{"value": 10**5_000}]
        with self.assertRaisesRegex(ValidationError, "canonical JSON") as raised:
            ReferenceBundle.from_dict(oversized_integer, context)
        self.assertNotIn("4300 digits", str(raised.exception))

    def test_enrichment_result_rehydrates_one_bundle_per_variant(self) -> None:
        manifest = fixture_manifest()
        bundle = ReferenceBundle.create(
            variant_id=manifest.variants[0].variant_id,
            context=manifest.context,
            sequence=None,
            elements=(),
            raw_features=(),
            receipts=(),
            warnings=(),
        )
        result = EnrichmentResult(manifest, (bundle,), ())

        self.assertEqual(EnrichmentResult.from_dict(result.to_dict()), result)

        substituted_context = replace(
            manifest.context,
            source_version=f"{manifest.context.source_version}-substituted",
        )
        self.assertEqual(substituted_context.key, manifest.context.key)
        substituted_bundle = ReferenceBundle.create(
            variant_id=manifest.variants[0].variant_id,
            context=substituted_context,
            sequence=None,
            elements=(),
            raw_features=(),
            receipts=(),
            warnings=(),
        )
        with self.assertRaisesRegex(ValidationError, "exactly match the manifest"):
            EnrichmentResult(manifest, (substituted_bundle,), ())

    def test_enrichment_manifest_shape_and_counts_are_bounded_before_hydration(self) -> None:
        manifest = fixture_manifest()
        bundle = ReferenceBundle.create(
            variant_id=manifest.variants[0].variant_id,
            context=manifest.context,
            sequence=None,
            elements=(),
            raw_features=(),
            receipts=(),
            warnings=(),
        )
        base = EnrichmentResult(manifest, (bundle,), ()).to_dict()
        malformed_values = (
            (
                [{}] * (MAX_ENRICHED_ELEMENTS + 1),
                "candidate elements exceed their hard ceiling",
            ),
            ((), "candidate_elements must be an exact array"),
            ([[]], "candidate elements must be exact JSON objects"),
        )
        for candidate_elements, message in malformed_values:
            malformed = copy.deepcopy(base)
            malformed["manifest"]["candidate_elements"] = candidate_elements
            with (
                self.subTest(message=message),
                patch(
                    "glio_noncode.data_sources.CaseManifest.from_dict",
                    side_effect=AssertionError("manifest hydration must not be reached"),
                ) as hydrate,
                self.assertRaisesRegex(ValidationError, message),
            ):
                EnrichmentResult.from_dict(malformed)
            hydrate.assert_not_called()

        too_many_variants = copy.deepcopy(base)
        too_many_variants["manifest"]["variants"] = [
            copy.deepcopy(base["manifest"]["variants"][0])
            for _ in range(MAX_REFERENCE_VARIANTS + 1)
        ]
        with (
            patch(
                "glio_noncode.data_sources.CaseManifest.from_dict",
                side_effect=AssertionError("manifest hydration must not be reached"),
            ) as hydrate,
            self.assertRaisesRegex(ValidationError, "variants exceed their hard ceiling"),
        ):
            EnrichmentResult.from_dict(too_many_variants)
        hydrate.assert_not_called()

        missing_bundle = copy.deepcopy(base)
        missing_bundle["bundles"] = []
        with (
            patch(
                "glio_noncode.data_sources.CaseManifest.from_dict",
                side_effect=AssertionError("manifest hydration must not be reached"),
            ) as hydrate,
            self.assertRaisesRegex(
                ValidationError,
                "exactly one bundle per manifest variant",
            ),
        ):
            EnrichmentResult.from_dict(missing_bundle)
        hydrate.assert_not_called()

    def test_enrichment_bundle_work_is_bounded_before_manifest_hydration(self) -> None:
        manifest = fixture_manifest()
        bundle = ReferenceBundle.create(
            variant_id=manifest.variants[0].variant_id,
            context=manifest.context,
            sequence=None,
            elements=(),
            raw_features=(),
            receipts=(),
            warnings=(),
        )
        base = EnrichmentResult(manifest, (bundle,), ()).to_dict()

        oversized_nested_array = copy.deepcopy(base)
        oversized_nested_array["bundles"][0]["raw_features"] = [
            {}
        ] * (MAX_REFERENCE_FEATURES + 1)
        with (
            patch(
                "glio_noncode.data_sources.CaseManifest.from_dict",
                side_effect=AssertionError("manifest hydration must not be reached"),
            ) as hydrate,
            self.assertRaisesRegex(ValidationError, "raw features exceed their hard ceiling"),
        ):
            EnrichmentResult.from_dict(oversized_nested_array)
        hydrate.assert_not_called()

        oversized_receipts = copy.deepcopy(base)
        oversized_receipts["bundles"][0]["receipts"] = [
            {}
        ] * (MAX_REFERENCE_RECEIPTS + 1)
        with (
            patch(
                "glio_noncode.data_sources.CaseManifest.from_dict",
                side_effect=AssertionError("manifest hydration must not be reached"),
            ) as hydrate,
            self.assertRaisesRegex(ValidationError, "receipts exceed their hard ceiling"),
        ):
            EnrichmentResult.from_dict(oversized_receipts)
        hydrate.assert_not_called()

        aggregate_warnings = copy.deepcopy(base)
        second_variant = copy.deepcopy(base["manifest"]["variants"][0])
        second_variant["variant_id"] = "variant-warning-2"
        second_bundle = copy.deepcopy(base["bundles"][0])
        second_bundle["variant_id"] = second_variant["variant_id"]
        first_warning_count = MAX_REFERENCE_WARNINGS // 2 + 1
        aggregate_warnings["manifest"]["variants"].append(second_variant)
        aggregate_warnings["bundles"].append(second_bundle)
        aggregate_warnings["bundles"][0]["warnings"] = [
            f"warning-{index}" for index in range(first_warning_count)
        ]
        aggregate_warnings["bundles"][1]["warnings"] = [
            f"warning-{index}"
            for index in range(first_warning_count, MAX_REFERENCE_WARNINGS + 1)
        ]
        with (
            patch(
                "glio_noncode.data_sources.CaseManifest.from_dict",
                side_effect=AssertionError("manifest hydration must not be reached"),
            ) as hydrate,
            self.assertRaisesRegex(
                ValidationError,
                "aggregate bundle warning occurrences exceed their hard ceiling",
            ),
        ):
            EnrichmentResult.from_dict(aggregate_warnings)
        hydrate.assert_not_called()

        aggregate = copy.deepcopy(base)
        aggregate["manifest"]["candidate_elements"] = []
        aggregate["manifest"]["variants"] = []
        aggregate["bundles"] = []
        remaining = MAX_ENRICHED_ELEMENTS + 1
        index = 0
        while remaining:
            element_count = min(MAX_REFERENCE_FEATURES, remaining)
            variant = copy.deepcopy(base["manifest"]["variants"][0])
            variant["variant_id"] = f"variant-{index}"
            raw_bundle = copy.deepcopy(base["bundles"][0])
            raw_bundle["variant_id"] = variant["variant_id"]
            raw_bundle["elements"] = [{}] * element_count
            aggregate["manifest"]["variants"].append(variant)
            aggregate["bundles"].append(raw_bundle)
            remaining -= element_count
            index += 1
        with (
            patch(
                "glio_noncode.data_sources.CaseManifest.from_dict",
                side_effect=AssertionError("manifest hydration must not be reached"),
            ) as hydrate,
            self.assertRaisesRegex(
                ValidationError,
                "aggregate bundle element occurrences exceed their hard ceiling",
            ),
        ):
            EnrichmentResult.from_dict(aggregate)
        hydrate.assert_not_called()

        aggregate_raw_features = copy.deepcopy(aggregate)
        for raw_bundle in aggregate_raw_features["bundles"]:
            raw_bundle["raw_features"] = raw_bundle["elements"]
            raw_bundle["elements"] = []
        with (
            patch(
                "glio_noncode.data_sources.CaseManifest.from_dict",
                side_effect=AssertionError("manifest hydration must not be reached"),
            ) as hydrate,
            self.assertRaisesRegex(
                ValidationError,
                "aggregate bundle raw feature occurrences exceed their hard ceiling",
            ),
        ):
            EnrichmentResult.from_dict(aggregate_raw_features)
        hydrate.assert_not_called()

    def test_enrichment_bytes_and_sequence_work_are_bounded_before_hydration(self) -> None:
        base_manifest = fixture_manifest()
        second_variant = replace(
            base_manifest.variants[0],
            variant_id="variant-enrichment-budget-2",
            start=base_manifest.variants[0].start + 10,
            end=base_manifest.variants[0].end + 10,
        )
        manifest = replace(
            base_manifest,
            variants=(base_manifest.variants[0], second_variant),
        )

        def sequence_bundle(index: int) -> ReferenceBundle:
            variant = manifest.variants[index]
            receipt = FetchReceipt(
                source_id="SRC-UCSC-REST",
                source_version="fixture-1",
                url=f"https://ucsc.example/sequence/{index}",
                request_hash=content_hash({"request": index}),
                response_hash=content_hash({"response": index}),
                status=FetchStatus.FETCHED,
                http_status=200,
                attempts=1,
                retrieved_at="2026-08-20T00:00:00+00:00",
                elapsed_seconds=0.001,
                cache_expires_at=None,
            )
            sequence = SequenceSlice(
                assembly=manifest.context.genome_build,
                chromosome=variant.chromosome,
                start=variant.start,
                end=variant.start + 3,
                sequence="ACGT",
                source_id=receipt.source_id,
                receipt=receipt,
            )
            return ReferenceBundle.create(
                variant_id=variant.variant_id,
                context=manifest.context,
                sequence=sequence,
                elements=(),
                raw_features=(),
                receipts=(receipt,),
                warnings=(),
            )

        result = EnrichmentResult(
            manifest,
            (sequence_bundle(0), sequence_bundle(1)),
            (),
        )
        raw = result.to_dict()
        cases = (
            (
                ReferenceRetrievalLimits(max_total_sequence_bp=7),
                "aggregate sequence work exceeds its configured base-pair ceiling",
            ),
            (
                ReferenceRetrievalLimits(
                    max_total_canonical_bytes=len(canonical_bytes(raw)) - 1,
                ),
                "configured canonical byte ceiling",
            ),
        )
        for limits, expected_error in cases:
            with (
                self.subTest(expected_error=expected_error),
                patch(
                    "glio_noncode.data_sources.ReferenceBundle.from_dict",
                    side_effect=AssertionError("bundle hydration must not be reached"),
                ) as hydrate,
                self.assertRaisesRegex(ValidationError, expected_error),
            ):
                EnrichmentResult.from_dict(raw, limits=limits)
            hydrate.assert_not_called()

    def test_enrichment_loader_counts_top_level_warnings_before_whole_encoding(self) -> None:
        manifest = fixture_manifest()
        warning = "candidate materialization abstained: " + "x" * 1_024
        bundle = ReferenceBundle.create(
            variant_id=manifest.variants[0].variant_id,
            context=manifest.context,
            sequence=None,
            elements=(),
            raw_features=(),
            receipts=(),
            warnings=(warning,),
        )
        raw = EnrichmentResult(manifest, (bundle,), (warning,)).to_dict()
        legacy_component_size = len(canonical_bytes(raw["manifest"])) + len(
            canonical_bytes(raw["bundles"][0])
        )
        empty_bundle_projection = dict(raw) | {"bundles": []}
        self.assertLessEqual(
            len(canonical_bytes(empty_bundle_projection)),
            legacy_component_size,
        )
        self.assertGreater(len(canonical_bytes(raw)), legacy_component_size)
        original_canonical = data_sources_module._validated_canonical_bytes
        encoded_labels: list[str] = []

        def guarded_canonical(value, label):
            encoded_labels.append(label)
            if label == "enrichment result":
                raise AssertionError("whole-result encoding must not be reached")
            return original_canonical(value, label)

        with (
            patch(
                "glio_noncode.data_sources._validated_canonical_bytes",
                side_effect=guarded_canonical,
            ),
            patch(
                "glio_noncode.data_sources.CaseManifest.from_dict",
                side_effect=AssertionError("manifest hydration must not be reached"),
            ) as manifest_hydration,
            patch(
                "glio_noncode.data_sources.ReferenceBundle.from_dict",
                side_effect=AssertionError("bundle hydration must not be reached"),
            ) as bundle_hydration,
            self.assertRaisesRegex(ValidationError, "configured canonical byte ceiling"),
        ):
            EnrichmentResult.from_dict(
                raw,
                limits=ReferenceRetrievalLimits(
                    max_total_canonical_bytes=legacy_component_size,
                ),
            )
        self.assertIn("enrichment reference bundle", encoded_labels)
        manifest_hydration.assert_not_called()
        bundle_hydration.assert_not_called()

        malformed_warning_cases = (
            ([warning, 1], "must contain exact strings"),
            ([warning, warning], "must be unique"),
            ([""], "must be a non-empty string"),
        )
        for malformed_warnings, expected_error in malformed_warning_cases:
            malformed = copy.deepcopy(raw)
            malformed["warnings"] = malformed_warnings
            with (
                self.subTest(expected_error=expected_error),
                patch(
                    "glio_noncode.data_sources.CaseManifest.from_dict",
                    side_effect=AssertionError("manifest hydration must not be reached"),
                ) as hydrate,
                self.assertRaisesRegex(ValidationError, expected_error),
            ):
                EnrichmentResult.from_dict(malformed)
            hydrate.assert_not_called()

    def test_enrichment_loader_honors_every_downward_configured_shape_limit(self) -> None:
        base_manifest = fixture_manifest()
        second_variant = replace(
            base_manifest.variants[0],
            variant_id="variant-configured-limit-2",
            start=base_manifest.variants[0].start + 10,
            end=base_manifest.variants[0].end + 10,
        )
        two_variant_manifest = replace(
            base_manifest,
            variants=(base_manifest.variants[0], second_variant),
        )
        empty_bundles = tuple(
            ReferenceBundle.create(
                variant_id=variant.variant_id,
                context=two_variant_manifest.context,
                sequence=None,
                elements=(),
                raw_features=(),
                receipts=(),
                warnings=(),
            )
            for variant in two_variant_manifest.variants
        )
        two_variant_raw = EnrichmentResult(
            two_variant_manifest,
            empty_bundles,
            (),
        ).to_dict()

        second_element = replace(
            base_manifest.candidate_elements[0],
            element_id="enhancer-demo-002",
        )
        two_element_manifest = replace(
            base_manifest,
            candidate_elements=tuple(
                sorted(
                    (*base_manifest.candidate_elements, second_element),
                    key=lambda item: item.element_id,
                )
            ),
        )
        two_element_bundle = ReferenceBundle.create(
            variant_id=two_element_manifest.variants[0].variant_id,
            context=two_element_manifest.context,
            sequence=None,
            elements=(),
            raw_features=(),
            receipts=(),
            warnings=(),
        )
        two_element_raw = EnrichmentResult(
            two_element_manifest,
            (two_element_bundle,),
            (),
        ).to_dict()

        two_feature_bundle = ReferenceBundle.create(
            variant_id=base_manifest.variants[0].variant_id,
            context=base_manifest.context,
            sequence=None,
            elements=(),
            raw_features=({"row": 1}, {"row": 2}),
            receipts=(),
            warnings=(),
        )
        two_feature_raw = EnrichmentResult(
            base_manifest,
            (two_feature_bundle,),
            (),
        ).to_dict()

        cases = (
            (
                two_variant_raw,
                ReferenceRetrievalLimits(max_variants=1),
                "configured variant ceiling",
            ),
            (
                two_element_raw,
                ReferenceRetrievalLimits(max_total_elements=1),
                "configured total ceiling",
            ),
            (
                two_feature_raw,
                ReferenceRetrievalLimits(max_features_per_variant=1),
                "configured per-variant ceiling",
            ),
        )
        for raw, limits, expected_error in cases:
            with (
                self.subTest(expected_error=expected_error),
                patch(
                    "glio_noncode.data_sources.CaseManifest.from_dict",
                    side_effect=AssertionError("manifest hydration must not be reached"),
                ) as hydrate,
                self.assertRaisesRegex(ValidationError, expected_error),
            ):
                EnrichmentResult.from_dict(raw, limits=limits)
            hydrate.assert_not_called()

    def test_direct_enrichment_size_check_stops_before_later_bundle_encoding(self) -> None:
        base_manifest = fixture_manifest()
        second_variant = replace(
            base_manifest.variants[0],
            variant_id="variant-progressive-construction-2",
            start=base_manifest.variants[0].start + 10,
            end=base_manifest.variants[0].end + 10,
        )
        manifest = replace(
            base_manifest,
            variants=(base_manifest.variants[0], second_variant),
        )
        bundles = tuple(
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
        empty_projection = {
            "manifest": manifest.to_dict(),
            "bundles": [],
            "warnings": [],
            "content_address": "sha256:" + "0" * 64,
        }
        first_bundle_size = len(canonical_bytes(bundles[0].to_dict()))
        progressive_limit = len(canonical_bytes(empty_projection)) + first_bundle_size - 1
        original_to_dict = ReferenceBundle.to_dict
        encoded_variants: list[str] = []

        def guarded_to_dict(bundle: ReferenceBundle) -> dict[str, object]:
            encoded_variants.append(bundle.variant_id)
            if bundle.variant_id == second_variant.variant_id:
                raise AssertionError("later bundle encoding must not be reached")
            return original_to_dict(bundle)

        with (
            patch(
                "glio_noncode.data_sources.MAX_ENRICHMENT_CANONICAL_BYTES",
                progressive_limit,
            ),
            patch.object(ReferenceBundle, "to_dict", guarded_to_dict),
            self.assertRaisesRegex(ValidationError, "hard canonical byte ceiling"),
        ):
            EnrichmentResult(manifest, bundles, ())
        self.assertEqual(encoded_variants, [manifest.variants[0].variant_id])

    def test_live_enrichment_projects_exact_closure_before_later_retrievals(self) -> None:
        base_manifest = fixture_manifest()
        second_variant = replace(
            base_manifest.variants[0],
            variant_id="variant-progressive-live-2",
            start=base_manifest.variants[0].start + 10,
            end=base_manifest.variants[0].end + 10,
        )
        manifest = replace(
            base_manifest,
            variants=(base_manifest.variants[0], second_variant),
        )
        warning = "candidate materialization abstained: " + "x" * 512
        first_bundle = ReferenceBundle.create(
            variant_id=manifest.variants[0].variant_id,
            context=manifest.context,
            sequence=None,
            elements=(),
            raw_features=(),
            receipts=(),
            warnings=(warning,),
        )
        second_bundle = ReferenceBundle.create(
            variant_id=manifest.variants[1].variant_id,
            context=manifest.context,
            sequence=None,
            elements=(),
            raw_features=(),
            receipts=(),
            warnings=(),
        )
        with tempfile.TemporaryDirectory() as directory:
            client = SourceClient(
                _catalog(),
                cache_root=directory,
                transport=SequenceTransport([]),
            )
            projected_manifest = replace(
                manifest,
                input_versions=dict(manifest.input_versions)
                | {
                    "live_reference_catalog": client.catalog.manifest()[
                        "content_address"
                    ]
                },
            )
            projected = {
                "manifest": projected_manifest.to_dict(),
                "bundles": [first_bundle.to_dict()],
                "warnings": [warning],
                "content_address": "sha256:" + "0" * 64,
            }
            limits = ReferenceRetrievalLimits(
                max_total_canonical_bytes=len(canonical_bytes(projected)) - 1,
            )
            retriever = PublicReferenceRetriever(client, limits=limits)
            calls: list[str] = []

            def retrieve(
                variant,
                context,
                *,
                window_bp=None,
                _external_integrity_guard=None,
            ):
                del context, window_bp, _external_integrity_guard
                calls.append(variant.variant_id)
                return (
                    first_bundle
                    if variant.variant_id == manifest.variants[0].variant_id
                    else second_bundle
                )

            with (
                patch.object(retriever, "retrieve", side_effect=retrieve),
                self.assertRaisesRegex(ValidationError, "configured canonical byte ceiling"),
            ):
                retriever.enrich_manifest(manifest)
        self.assertEqual(calls, [manifest.variants[0].variant_id])

    def test_live_enrichment_rejects_aggregate_occurrences_before_later_retrievals(
        self,
    ) -> None:
        base_manifest = fixture_manifest()
        second_variant = replace(
            base_manifest.variants[0],
            variant_id="variant-progressive-occurrences-2",
            start=base_manifest.variants[0].start + 10,
            end=base_manifest.variants[0].end + 10,
        )
        manifest = replace(
            base_manifest,
            variants=(base_manifest.variants[0], second_variant),
        )
        second_element = replace(
            manifest.candidate_elements[0],
            element_id="enhancer-progressive-occurrences-2",
        )
        elements = tuple(
            sorted(
                (manifest.candidate_elements[0], second_element),
                key=lambda item: item.element_id,
            )
        )
        receipt = FetchReceipt(
            source_id="SRC-UCSC-REST",
            source_version="fixture-1",
            url="https://ucsc.example/aggregate-preflight",
            request_hash=content_hash({"request": "aggregate-preflight"}),
            response_hash=content_hash({"response": "aggregate-preflight"}),
            status=FetchStatus.FETCHED,
            http_status=200,
            attempts=1,
            retrieved_at="2026-08-20T00:00:00+00:00",
            elapsed_seconds=0.001,
            cache_expires_at=None,
        )

        def bundle(
            *,
            elements: tuple = (),
            raw_features: tuple = (),
            receipts: tuple = (),
            warnings: tuple = (),
        ) -> ReferenceBundle:
            return ReferenceBundle.create(
                variant_id=manifest.variants[0].variant_id,
                context=manifest.context,
                sequence=None,
                elements=elements,
                raw_features=raw_features,
                receipts=receipts,
                warnings=warnings,
            )

        cases = (
            (
                bundle(elements=elements),
                "MAX_ENRICHED_ELEMENTS",
                1,
                "element occurrences",
            ),
            (
                bundle(raw_features=({"row": 1}, {"row": 2})),
                "MAX_ENRICHED_ELEMENTS",
                1,
                "raw feature occurrences",
            ),
            (
                bundle(receipts=(receipt,)),
                "MAX_REFERENCE_RECEIPTS",
                0,
                "receipt occurrences",
            ),
            (
                bundle(warnings=("first-bundle warning",)),
                "MAX_REFERENCE_WARNINGS",
                0,
                "warning occurrences",
            ),
        )
        second_bundle = ReferenceBundle.create(
            variant_id=manifest.variants[1].variant_id,
            context=manifest.context,
            sequence=None,
            elements=(),
            raw_features=(),
            receipts=(),
            warnings=(),
        )
        with tempfile.TemporaryDirectory() as directory:
            retriever = PublicReferenceRetriever(
                SourceClient(
                    _catalog(),
                    cache_root=directory,
                    transport=SequenceTransport([]),
                )
            )
            for first_bundle, constant_name, ceiling, expected_error in cases:
                with (
                    self.subTest(expected_error=expected_error),
                    patch.object(data_sources_module, constant_name, ceiling),
                    patch.object(
                        retriever,
                        "retrieve",
                        side_effect=(first_bundle, second_bundle),
                    ) as retrieve,
                    self.assertRaisesRegex(ValidationError, expected_error),
                ):
                    retriever.enrich_manifest(manifest)
                self.assertEqual(retrieve.call_count, 1)

    def test_cache_entry_is_bound_to_the_exact_requested_url(self) -> None:
        source = _source(max_response_bytes=1_024)
        request_hash = content_hash({"request": "one"})
        body = b'{"ok":true}'
        with tempfile.TemporaryDirectory() as directory:
            cache = SourceCache(directory)
            cache.put(
                request_hash=request_hash,
                source=source,
                url="https://ensembl.example/one",
                body=body,
                content_type="application/json",
                ttl_seconds=60,
            )

            self.assertIsNotNone(
                cache.get(
                    request_hash,
                    source=source,
                    expected_url="https://ensembl.example/one",
                    max_response_bytes=1_024,
                )
            )
            self.assertIsNone(
                cache.get(
                    request_hash,
                    source=source,
                    expected_url="https://ensembl.example/two",
                    max_response_bytes=1_024,
                )
            )

    def test_local_spacing_refusal_records_zero_network_attempts(self) -> None:
        source = _source()

        class RefusingLimiter:
            @staticmethod
            def wait() -> None:
                raise SourceRateLimitError("local spacing refused the request")

        with tempfile.TemporaryDirectory() as directory:
            client = SourceClient(
                SourceCatalog((source,)),
                cache_root=directory,
                transport=SequenceTransport([]),
            )
            client._limiters[source.source_id] = RefusingLimiter()  # type: ignore[assignment]
            with self.assertRaises(SourceRateLimitError) as captured:
                client.fetch_json(source.source_id, "/limited", cache=False)

        self.assertEqual(captured.exception.receipt.attempts, 0)
        self.assertIsNone(captured.exception.receipt.http_status)

    def test_out_of_interval_reference_rows_are_an_explicit_abstention(self) -> None:
        catalog = _catalog()
        manifest = fixture_manifest()
        variant = manifest.variants[0]
        query_start = variant.start - 10
        query_end = variant.end + 10
        sequence_url = (
            "https://ucsc.example/getData/sequence?chrom=chr7"
            f"&end={query_end}&genome=hg38&start={query_start - 1}"
        )
        overlap_url = (
            "https://ensembl.example/overlap/region/homo_sapiens/"
            f"7:{query_start}-{query_end}?feature=gene&feature=motif&feature=regulatory"
        )
        transport = FakeTransport(
            {
                sequence_url: {"dna": "A" * (query_end - query_start + 1)},
                overlap_url: [
                    {
                        "feature_type": "gene",
                        "id": "GENE_A",
                        "seq_region_name": "7",
                        "start": query_end + 10,
                        "end": query_end + 20,
                    }
                ],
            }
        )
        with tempfile.TemporaryDirectory() as directory:
            bundle = PublicReferenceRetriever(
                SourceClient(catalog, cache_root=directory, transport=transport),
                window_bp=10,
            ).retrieve(variant, manifest.context)

        self.assertEqual(bundle.elements, ())
        self.assertEqual(len(bundle.raw_features), 1)
        self.assertEqual(len(bundle.receipts), 2)
        self.assertTrue(
            any(
                item.startswith("candidate materialization abstained:")
                and "escaped the requested interval" in item
                for item in bundle.warnings
            )
        )

    def test_unknown_reference_rows_are_retained_only_as_materialization_abstentions(self) -> None:
        catalog = _catalog()
        manifest = fixture_manifest()
        variant = manifest.variants[0]
        query_start = variant.start - 10
        query_end = variant.end + 10
        sequence_url = (
            "https://ucsc.example/getData/sequence?chrom=chr7"
            f"&end={query_end}&genome=hg38&start={query_start - 1}"
        )
        overlap_url = (
            "https://ensembl.example/overlap/region/homo_sapiens/"
            f"7:{query_start}-{query_end}?feature=gene&feature=motif&feature=regulatory"
        )
        malformed_rows = (
            {"id": "missing-type", "start": variant.start, "end": variant.end},
            {
                "feature_type": "unexpected",
                "id": "unsupported-type",
                "start": variant.start,
                "end": variant.end,
            },
        )
        for row in malformed_rows:
            transport = FakeTransport(
                {
                    sequence_url: {"dna": "A" * (query_end - query_start + 1)},
                    overlap_url: [row],
                }
            )
            with tempfile.TemporaryDirectory() as directory:
                bundle = PublicReferenceRetriever(
                    SourceClient(catalog, cache_root=directory, transport=transport),
                    window_bp=10,
                ).retrieve(variant, manifest.context)

            with self.subTest(row=row):
                self.assertEqual(bundle.elements, ())
                self.assertEqual(tuple(bundle.raw_features), (row,))
                self.assertEqual(len(bundle.receipts), 2)
                self.assertTrue(
                    any(
                        item.startswith("candidate materialization abstained:")
                        and "missing or unsupported feature_type" in item
                        for item in bundle.warnings
                    )
                )
