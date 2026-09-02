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
from urllib.parse import urlsplit

from glio_noncode.data_sources import (
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
from glio_noncode.serialization import content_hash

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
        invalid_bodies = (b'{"score":NaN}', b'{"id":1,"id":2}')
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
            context_key="GRCh38|glioma|adult|stem_like|unspecified|untreated",
            sequence=sequence,
            elements=(),
            raw_features=(feature,),
            receipts=(receipt,),
            warnings=(),
        )
        feature["nested"].append(2)
        self.assertEqual(bundle.raw_features[0]["nested"], [1])
        with self.assertRaisesRegex(ValidationError, "does not match its payload"):
            replace(bundle, content_address="sha256:" + "0" * 64)

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
        self.assertEqual(len(bundle.receipts), 2)
        self.assertTrue(any("escaped the requested interval" in item for item in bundle.warnings))
