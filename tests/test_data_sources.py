from __future__ import annotations

import json
import tempfile
import unittest
from urllib.parse import urlsplit

from glio_noncode.data_sources import (
    EnsemblRestClient,
    PublicReferenceRetriever,
    SourceAccess,
    SourceCatalog,
    SourceClient,
    SourceKind,
    SourceSpec,
    TransportResponse,
    UcscRestClient,
)
from glio_noncode.errors import SourceError

from .helpers import fixture_manifest


class FakeTransport:
    def __init__(self, responses: dict[str, object]) -> None:
        self.responses = responses
        self.calls: list[str] = []

    def request(self, method: str, url: str, headers: dict[str, str], timeout_seconds: float) -> TransportResponse:
        self.calls.append(url)
        value = self.responses[url]
        if isinstance(value, bytes):
            body = value
            content_type = "text/plain"
        else:
            body = json.dumps(value).encode("utf-8")
            content_type = "application/json"
        return TransportResponse(200, url, {"content-type": content_type}, body, 0.001)


def test_catalog() -> SourceCatalog:
    return SourceCatalog(
        (
            SourceSpec(
                source_id="SRC-ENSEMBL-REST",
                name="Ensembl",
                kind=SourceKind.REFERENCE_ANNOTATION,
                access=SourceAccess.PUBLIC_API,
                base_url="https://ensembl.example",
                canonical_url="https://ensembl.example/docs",
                version="fixture-1",
                license="fixture",
                rate_limit_per_minute=100000,
                max_region_bp=5_000_000,
            ),
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
        catalog = test_catalog()
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
        catalog = test_catalog()
        url = "https://ucsc.example/getData/sequence?genome=hg38&chrom=chr7&start=99&end=200"
        transport = FakeTransport({url: {"dna": "A" * 101, "start": 99, "end": 200}})
        with tempfile.TemporaryDirectory() as directory:
            payload = UcscRestClient(SourceClient(catalog, cache_root=directory, transport=transport)).sequence(
                "7", 100, 200, genome_build="GRCh38"
            )
            self.assertEqual(payload.value["dna"], "A" * 101)
            self.assertEqual(urlsplit(transport.calls[0]).query, "genome=hg38&chrom=chr7&start=99&end=200")

    def test_live_reference_retriever_converts_real_shaped_payloads_to_elements(self) -> None:
        catalog = test_catalog()
        manifest = fixture_manifest()
        variant = manifest.variants[0]
        query_start = variant.start - 10
        query_end = variant.end + 10
        sequence_url = f"https://ucsc.example/getData/sequence?genome=hg38&chrom=chr7&start={query_start - 1}&end={query_end}"
        overlap_url = f"https://ensembl.example/overlap/region/homo_sapiens/7:{query_start}-{query_end}?feature=regulatory&feature=motif&feature=gene"
        transport = FakeTransport(
            {
                sequence_url: {"dna": "A" * (query_end - query_start + 1)},
                overlap_url: [
                    {"feature_type": "gene", "id": "ENSG000001", "external_name": "GENE_A", "start": query_start, "end": query_end},
                    {"feature_type": "regulatory", "id": "ENSR000001", "seq_region_name": "7", "start": variant.start - 2, "end": variant.end + 2, "description": "enhancer"},
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

    def test_failed_source_request_carries_a_non_negative_failure_receipt(self) -> None:
        catalog = test_catalog()
        transport = FakeTransport({})
        with tempfile.TemporaryDirectory() as directory:
            client = SourceClient(catalog, cache_root=directory, transport=transport)
            with self.assertRaises(SourceError) as captured:
                client.fetch_json("SRC-ENSEMBL-REST", "/missing")
            receipt = captured.exception.receipt
            self.assertIsNotNone(receipt)
            self.assertEqual(receipt.status.value, "failed")
            self.assertIn("not a negative", receipt.warnings[0])
