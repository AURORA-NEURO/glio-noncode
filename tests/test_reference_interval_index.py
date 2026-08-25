from __future__ import annotations

import json
import tempfile
import unittest
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread

from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.reference_interval_index import (
    ContextQueryMode,
    PublicReferenceRecord,
    ReferenceIndexQuery,
    ReferenceIndexQueryState,
    ReferenceIntervalIndex,
    build_reference_interval_index,
    match_context,
    reference_interval_index_capabilities,
    reference_interval_index_schema,
)


CONTEXT = "GRCh38|glioma|adult|stem_like|unknown|unknown"
GENERAL = "GRCh38|all|all|all|unknown|unknown"
FOREIGN = "GRCh38|brain|adult|astrocyte|unknown|unknown"
OTHER_BUILD = "GRCh37|glioma|adult|stem_like|unknown|unknown"


def _rows() -> list[dict[str, object]]:
    return [
        {
            "record_id": "exact-1",
            "chromosome": "7",
            "start": 100,
            "end": 120,
            "context_key": CONTEXT,
            "source_id": "atlas-a",
            "track_type": "open_chromatin",
            "state": "supported",
            "payload": {"score": 0.91, "sample_id": "must-not-escape"},
            "tags": ["core", "atac"],
        },
        {
            "record_id": "general-1",
            "chromosome": "chr7",
            "start": 110,
            "end": 135,
            "context_key": GENERAL,
            "source_id": "atlas-a",
            "track_type": "open_chromatin",
            "state": "supported",
            "payload": {"score": 0.52},
        },
        {
            "record_id": "foreign-1",
            "chromosome": "7",
            "start": 112,
            "end": 118,
            "context_key": FOREIGN,
            "source_id": "atlas-a",
            "track_type": "open_chromatin",
            "state": "supported",
            "payload": {"score": 0.12},
        },
        {
            "record_id": "other-track",
            "chromosome": "7",
            "start": 105,
            "end": 108,
            "context_key": CONTEXT,
            "source_id": "atlas-b",
            "track_type": "methylation",
            "state": "absent",
            "payload": {"fraction": 0.1},
        },
        {
            "record_id": "other-build",
            "chromosome": "7",
            "start": 112,
            "end": 118,
            "context_key": OTHER_BUILD,
            "source_id": "atlas-a",
            "track_type": "open_chromatin",
            "state": "supported",
            "payload": {"score": 0.2},
        },
    ]


class ReferenceIntervalIndexTests(unittest.TestCase):
    def test_build_is_columnar_sorted_and_public_safe(self) -> None:
        report = build_reference_interval_index(
            reversed(_rows()),
            index_id="fixture-index",
            assembly="GRCh38",
            block_size=2,
        )
        self.assertTrue(report.accepted, report.to_dict())
        index = report.index
        self.assertEqual(index.record_count, 5)
        self.assertEqual(index.chromosome_count, 1)
        self.assertEqual(index.columns.record_ids, tuple(sorted(index.columns.record_ids, key=lambda value: next(
            row["start"] for row in _rows() if row["record_id"] == value
        ))))
        self.assertNotIn("sample_id", index.record_at(0).payload)
        self.assertEqual(index.columns.row_count, len(index.columns.starts))
        self.assertEqual(len(index.blocks["chr7"]), 3)
        self.assertTrue(index.content_address.startswith("reference-index:"))
        contig_record = PublicReferenceRecord.from_mapping(
            {
                "record_id": "contig-alias",
                "contig": "8",
                "start": 1,
                "end": 2,
                "context_key": CONTEXT,
            }
        )
        self.assertEqual(contig_record.chromosome, "chr8")

    def test_lattice_query_prefers_exact_context_over_general_context(self) -> None:
        index = build_reference_interval_index(_rows(), index_id="fixture-index").index
        query = ReferenceIndexQuery.from_mapping(
            {
                "chromosome": "7",
                "start": 112,
                "end": 116,
                "context_key": CONTEXT,
            }
        )
        report = index.query(query)
        self.assertEqual(report.state, ReferenceIndexQueryState.SUPPORTED)
        self.assertEqual(report.total_match_count, 2)
        self.assertEqual([match.record.record_id for match in report.matches], ["exact-1", "general-1"])
        self.assertEqual(report.matches[0].specificity, 6)
        self.assertEqual(report.matches[1].generalized_dimensions[:3], (
            "disease_class",
            "age_group",
            "cell_state",
        ))
        self.assertEqual(report.matches[0].overlap_bp, 5)

    def test_exact_mode_excludes_generalized_rows(self) -> None:
        index = build_reference_interval_index(_rows(), index_id="fixture-index").index
        report = index.query(
            ReferenceIndexQuery.from_mapping(
                {
                    "chromosome": "7",
                    "start": 112,
                    "end": 116,
                    "context_key": CONTEXT,
                    "mode": ContextQueryMode.EXACT.value,
                }
            )
        )
        self.assertEqual(report.total_match_count, 1)
        self.assertEqual(report.matches[0].record.record_id, "exact-1")
        self.assertEqual(report.filter_rejected_count, 0)

    def test_out_of_domain_is_distinct_from_absent(self) -> None:
        index = build_reference_interval_index(_rows(), index_id="fixture-index").index
        foreign = index.query(
            ReferenceIndexQuery.from_mapping(
                {
                    "chromosome": "7",
                    "start": 112,
                    "end": 116,
                    "context_key": "GRCh36|glioma|adult|stem_like|unknown|unknown",
                }
            )
        )
        absent = index.query(
            ReferenceIndexQuery.from_mapping(
                {
                    "chromosome": "8",
                    "start": 112,
                    "end": 116,
                    "context_key": CONTEXT,
                }
            )
        )
        self.assertEqual(foreign.state, ReferenceIndexQueryState.OUT_OF_DOMAIN)
        self.assertGreater(foreign.context_rejected_count, 0)
        self.assertEqual(absent.state, ReferenceIndexQueryState.ABSENT)
        self.assertEqual(absent.interval_candidate_count, 0)

    def test_filters_pagination_and_query_addresses_are_deterministic(self) -> None:
        index = build_reference_interval_index(_rows(), index_id="fixture-index").index
        query = ReferenceIndexQuery.from_mapping(
            {
                "chromosome": "7",
                "start": 100,
                "end": 140,
                "context_key": CONTEXT,
                "track_type": "open_chromatin",
                "limit": 1,
            }
        )
        first = index.query(query)
        second = index.query(query)
        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual(first.state, ReferenceIndexQueryState.TRUNCATED)
        self.assertTrue(first.accepted)
        self.assertEqual(first.total_match_count, 2)
        self.assertEqual(first.matches[0].record.track_type, "open_chromatin")
        self.assertTrue(any("bounded" in warning for warning in first.warnings))

    def test_block_pruning_does_not_drop_long_intervals(self) -> None:
        rows = [
            {
                "record_id": "long",
                "chromosome": "7",
                "start": 1,
                "end": 10000,
                "context_key": CONTEXT,
                "source_id": "source",
                "track_type": "track",
            }
        ]
        rows.extend(
            {
                "record_id": f"row-{index}",
                "chromosome": "7",
                "start": 20_000 + index * 10,
                "end": 20_005 + index * 10,
                "context_key": CONTEXT,
                "source_id": "source",
                "track_type": "track",
            }
            for index in range(20)
        )
        index = build_reference_interval_index(rows, block_size=2).index
        self.assertEqual(index.candidate_indices("7", 9_999, 10_001), (0,))
        report = index.query(
            ReferenceIndexQuery.from_mapping(
                {
                    "chromosome": "7",
                    "start": 9_999,
                    "end": 10_001,
                    "context_key": CONTEXT,
                }
            )
        )
        self.assertEqual(report.matches[0].record.record_id, "long")

    def test_context_matching_is_explicit_and_build_never_generalizes(self) -> None:
        exact = match_context(CONTEXT, CONTEXT, mode=ContextQueryMode.EXACT)
        generalized = match_context(GENERAL, CONTEXT, mode=ContextQueryMode.LATTICE)
        foreign_build = match_context(OTHER_BUILD, CONTEXT, mode=ContextQueryMode.LATTICE)
        wildcard = match_context(
            GENERAL,
            "GRCh38|glioma|*|stem_like|unknown|unknown",
            mode=ContextQueryMode.LATTICE,
        )
        self.assertTrue(exact.accepted)
        self.assertEqual(exact.specificity, 6)
        self.assertTrue(generalized.accepted)
        self.assertFalse(foreign_build.accepted)
        self.assertTrue(wildcard.accepted)
        self.assertIn("cell_state", wildcard.generalized_dimensions)
        mapped_query = ReferenceIndexQuery.from_mapping(
            {
                "chromosome": "7",
                "start": 112,
                "end": 116,
                "context": {
                    "genome_build": "GRCh38",
                    "disease_class": "glioma",
                    "age_group": "*",
                    "cell_state": "stem_like",
                },
            }
        )
        self.assertEqual(mapped_query.context_key, "GRCh38|glioma|*|stem_like|unknown|unknown")

    def test_build_rejects_invalid_rows_and_tracks_duplicates(self) -> None:
        rows = _rows() + [_rows()[0], {"record_id": "bad", "chromosome": "7", "start": 0, "end": 1}]
        report = build_reference_interval_index(rows, index_id="fixture-index")
        self.assertFalse(report.accepted)
        self.assertEqual(report.accepted_count, 5)
        self.assertEqual(report.warning_count, 1)
        self.assertEqual(report.error_count, 1)
        self.assertEqual(report.rejected_count, 2)
        self.assertEqual(report.issues[0].code, "duplicate_record")
        self.assertEqual(report.issues[1].code, "invalid_record")

    def test_round_trip_reverifies_columns_blocks_and_address(self) -> None:
        index = build_reference_interval_index(_rows(), block_size=2).index
        reopened = ReferenceIntervalIndex.from_dict(index.to_dict())
        self.assertEqual(reopened.content_address, index.content_address)
        self.assertEqual(reopened.to_dict(), index.to_dict())
        with self.assertRaises(Exception):
            tampered = index.to_dict()
            tampered["columns"]["starts"][0] = 999999
            ReferenceIntervalIndex.from_dict(tampered)

    def test_lattice_summary_is_addressed_without_rows(self) -> None:
        index = build_reference_interval_index(_rows(), index_id="fixture-index").index
        summary = index.context_lattice_summary()
        self.assertEqual(summary["index_id"], "fixture-index")
        self.assertEqual(summary["context_count"], 4)
        self.assertIn("specificity_histogram", summary)
        self.assertTrue(summary["content_address"].startswith("reference-context-lattice:"))

    def test_schema_capabilities_and_cli_round_trip(self) -> None:
        schema = reference_interval_index_schema()
        capabilities = reference_interval_index_capabilities()
        self.assertEqual(schema["version"], "reference-interval-index-schema-v1")
        self.assertIn("lattice", capabilities["context"])
        self.assertNotIn("agent", json.dumps(schema).lower())
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "rows.json"
            index_path = Path(directory) / "index.json"
            query_path = Path(directory) / "query.json"
            source.write_text(json.dumps({"records": _rows()}), encoding="utf-8")
            self.assertEqual(
                main(
                    [
                        "build-reference-index",
                        str(source),
                        "--index-id",
                        "cli-index",
                        "--block-size",
                        "2",
                        "--output",
                        str(index_path),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "query-reference-index",
                        str(index_path),
                        "--chromosome",
                        "7",
                        "--start",
                        "112",
                        "--end",
                        "116",
                        "--context-key",
                        CONTEXT,
                        "--output",
                        str(query_path),
                    ]
                ),
                0,
            )
            payload = json.loads(query_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["total_match_count"], 2)
            self.assertEqual(payload["matches"][0]["record"]["record_id"], "exact-1")

    def test_api_build_query_and_schema_routes(self) -> None:
        server = create_server("127.0.0.1", 0, ".glio-reference-index-test")
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = server.server_address
            connection = HTTPConnection(host, port, timeout=10)
            connection.request("GET", "/v1/reference/index/schema")
            schema_response = connection.getresponse()
            self.assertEqual(schema_response.status, 200)
            self.assertEqual(
                json.loads(schema_response.read().decode())["index_version"],
                "reference-interval-index-v1",
            )
            body = json.dumps({"index_id": "api-index", "records": _rows()}).encode()
            connection.request(
                "POST",
                "/v1/reference/index/build",
                body=body,
                headers={"Content-Type": "application/json", "Content-Length": str(len(body))},
            )
            build_response = connection.getresponse()
            self.assertEqual(build_response.status, 200)
            build_payload = json.loads(build_response.read().decode())
            query_body = json.dumps(
                {
                    "index": build_payload["index"],
                    "query": {
                        "chromosome": "7",
                        "start": 112,
                        "end": 116,
                        "context_key": CONTEXT,
                    },
                }
            ).encode()
            connection.request(
                "POST",
                "/v1/reference/index/query",
                body=query_body,
                headers={
                    "Content-Type": "application/json",
                    "Content-Length": str(len(query_body)),
                },
            )
            query_response = connection.getresponse()
            self.assertEqual(query_response.status, 200)
            query_payload = json.loads(query_response.read().decode())
            self.assertEqual(query_payload["total_match_count"], 2)
            connection.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
