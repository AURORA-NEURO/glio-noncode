from __future__ import annotations

import json
import tempfile
import unittest
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread

from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.cohort_benchmarks import (
    BenchmarkState,
    CalibrationConfig,
    CohortBenchmarkConfig,
    CohortBenchmarkRecord,
    LeakagePolicy,
    SelectiveRiskConfig,
    SplitConfig,
    SplitStrategy,
    TransportConfig,
    audit_cohort_leakage,
    benchmark_calibration,
    benchmark_selective_risk,
    benchmark_transport,
    build_cohort_split,
    cohort_benchmark_capabilities,
    cohort_benchmark_schema,
    run_cohort_benchmark,
)
from glio_noncode.serialization import content_hash


CONTEXT = "GRCh38|glioma|adult|stem_like|unknown|unknown"


def records(count: int = 30) -> list[dict[str, object]]:
    return [
        {
            "record_id": f"record-{index:03d}",
            "cohort_id": f"cohort-{index % 5}",
            "domain_id": "source" if (index // 2) % 2 == 0 else "target",
            "source_id": "source-a" if index % 3 else "source-b",
            "context_key": CONTEXT,
            "label": index % 2,
            "score": 0.9 if index % 2 else 0.1,
            "uncertainty": 0.05,
            "group_id": f"group-{index // 2}",
            "lineage_key": f"lineage-{index}",
            "feature_keys": ["feature-a", "feature-b", "feature-c"],
            "collected_at": f"2026-01-{(index % 28) + 1:02d}T00:00:00+00:00",
        }
        for index in range(count)
    ]


def typed_records(count: int = 30) -> tuple[CohortBenchmarkRecord, ...]:
    return tuple(CohortBenchmarkRecord.from_mapping(row) for row in records(count))


class CohortBenchmarkTests(unittest.TestCase):
    def test_record_contract_rejects_private_keys_and_is_addressed(self) -> None:
        record = CohortBenchmarkRecord.from_mapping(records(1)[0])
        self.assertTrue(record.content_address.startswith("cohort-benchmark-record:"))
        self.assertEqual(record.to_dict(), CohortBenchmarkRecord.from_mapping(record.to_dict()).to_dict())
        with self.assertRaises(Exception):
            CohortBenchmarkRecord.from_mapping(records(1)[0] | {"sample_id": "forbidden"})

    def test_group_split_keeps_groups_together_and_is_deterministic(self) -> None:
        selected = typed_records()
        config = SplitConfig(
            strategy=SplitStrategy.GROUP,
            seed="stable-seed",
            minimum_records_per_split=0,
        )
        first = build_cohort_split(selected, config)
        second = build_cohort_split(selected, config)
        self.assertEqual(first.to_dict(), second.to_dict())
        assignment = {
            record_id: split_name
            for split_name in ("train", "validation", "test")
            for record_id in first.ids_for(split_name)
        }
        for group in {record.group_id for record in selected}:
            group_splits = {
                assignment[record.record_id]
                for record in selected
                if record.group_id == group
            }
            self.assertLessEqual(len(group_splits), 1)

    def test_leakage_audit_blocks_lineage_cross_split(self) -> None:
        selected = typed_records(3)
        split_body = {
            "strategy": SplitStrategy.HASH,
            "seed": "manual",
            "train_ids": (selected[0].record_id,),
            "validation_ids": (selected[1].record_id,),
            "test_ids": (selected[2].record_id,),
            "group_assignments": {},
            "counts": {"train": 1, "validation": 1, "test": 1},
            "issues": (),
        }
        split = build_cohort_split(
            selected,
            SplitConfig(strategy=SplitStrategy.HASH, minimum_records_per_split=0),
        )
        manual = type(split)(
            strategy=SplitStrategy.HASH,
            seed="manual",
            train_ids=(selected[0].record_id,),
            validation_ids=(selected[1].record_id,),
            test_ids=(selected[2].record_id,),
            group_assignments={},
            counts={"train": 1, "validation": 1, "test": 1},
            issues=(),
            content_address=content_hash(split_body, prefix="cohort-split"),
        )
        duplicated_lineage = (
            selected[0],
            CohortBenchmarkRecord.from_mapping(
                records(3)[1] | {"lineage_key": selected[0].lineage_key}
            ),
            selected[2],
        )
        report = audit_cohort_leakage(
            duplicated_lineage,
            manual,
            LeakagePolicy(error_on_lineage_overlap=True),
        )
        self.assertEqual(report.state, BenchmarkState.BLOCKED)
        self.assertEqual(report.lineage_overlap_count, 1)
        self.assertIn("lineage_cross_split", {item.code for item in report.findings})

    def test_calibration_reports_reliability_and_brier_metrics(self) -> None:
        report = benchmark_calibration(
            typed_records(12),
            CalibrationConfig(
                bins=5,
                minimum_records=5,
                maximum_ece=0.15,
                maximum_mce=0.2,
                maximum_brier=0.1,
            ),
        )
        self.assertEqual(report.state, BenchmarkState.ACCEPTED)
        self.assertEqual(report.usable_count, 12)
        self.assertAlmostEqual(report.brier_score, 0.01, places=5)
        self.assertLessEqual(report.expected_calibration_error, 0.15)
        self.assertTrue(report.bins)

    def test_selective_risk_exposes_coverage_and_uncertainty_abstention(self) -> None:
        selected = list(typed_records(12))
        selected[0] = CohortBenchmarkRecord.from_mapping(
            records(12)[0] | {"uncertainty": 0.9}
        )
        report = benchmark_selective_risk(
            tuple(selected),
            SelectiveRiskConfig(
                minimum_coverage=0.5,
                maximum_risk=0.1,
                maximum_uncertainty=0.25,
                points=11,
                minimum_records=5,
            ),
        )
        self.assertEqual(report.state, BenchmarkState.ACCEPTED)
        self.assertIsNotNone(report.best_threshold)
        self.assertTrue(any(point.abstention_rate > 0 for point in report.points))
        self.assertGreaterEqual(report.area_under_risk_coverage, 0.0)

    def test_transport_reports_shift_and_review_state(self) -> None:
        selected = typed_records(12)
        accepted = benchmark_transport(
            selected,
            source_domain="source",
            target_domains=("target",),
            config=TransportConfig(minimum_records_per_domain=2),
        )
        self.assertEqual(accepted.state, BenchmarkState.ACCEPTED)
        self.assertEqual(accepted.accepted_domains, ("target",))
        shifted = tuple(
            CohortBenchmarkRecord.from_mapping(
                row
                | {
                    "domain_id": "target",
                    "label": 1,
                    "score": 0.99,
                }
            )
            for row in records(6)
        )
        reviewed = benchmark_transport(
            tuple(typed_records(6)) + shifted,
            source_domain="source",
            target_domains=("target",),
            config=TransportConfig(
                maximum_positive_rate_shift=0.05,
                maximum_score_shift=0.05,
                minimum_records_per_domain=2,
            ),
        )
        self.assertEqual(reviewed.state, BenchmarkState.REVIEW)
        self.assertIn("target", reviewed.review_domains)
        self.assertIn("positive_rate_shift_high", reviewed.pairs[0].issues)

    def test_full_suite_joins_all_planes_and_is_deterministic(self) -> None:
        config = CohortBenchmarkConfig(
            split=SplitConfig(
                strategy=SplitStrategy.TEMPORAL,
                minimum_records_per_split=1,
            ),
            calibration=CalibrationConfig(minimum_records=1, maximum_ece=0.2),
            selective_risk=SelectiveRiskConfig(minimum_records=1, maximum_risk=0.1),
            transport=TransportConfig(minimum_records_per_domain=1),
            source_domain="source",
            target_domains=("target",),
        )
        first = run_cohort_benchmark(records(), dataset_id="fixture-cohort", config=config)
        second = run_cohort_benchmark(records(), dataset_id="fixture-cohort", config=config)
        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual(first.state, BenchmarkState.ACCEPTED)
        self.assertEqual(first.evaluation_split, "test")
        self.assertEqual(first.transport_split, "all")
        self.assertEqual(first.leakage.state, BenchmarkState.ACCEPTED)

    def test_schema_capabilities_and_cli_surface(self) -> None:
        self.assertEqual(cohort_benchmark_schema()["version"], "cohort-benchmark-schema-v1")
        self.assertIn("risk_coverage_curve", cohort_benchmark_schema()["metrics"])
        self.assertTrue(cohort_benchmark_capabilities()["split"]["seeded_hash_assignment_is_deterministic"])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_path = root / "records.json"
            output_path = root / "benchmark.json"
            schema_path = root / "schema.json"
            input_path.write_text(json.dumps({"records": records()}), encoding="utf-8")
            self.assertEqual(
                main(
                    [
                        "cohort-benchmark",
                        str(input_path),
                        "--dataset-id",
                        "cli-cohort",
                        "--split-strategy",
                        "temporal",
                        "--minimum-records-per-split",
                        "1",
                        "--calibration-minimum-records",
                        "1",
                        "--selective-minimum-records",
                        "1",
                        "--transport-minimum-records",
                        "1",
                        "--source-domain",
                        "source",
                        "--target-domain",
                        "target",
                        "--output",
                        str(output_path),
                    ]
                ),
                0,
            )
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["state"], "accepted")
            self.assertEqual(
                main(["cohort-benchmark-schema", "--output", str(schema_path)]),
                0,
            )
            self.assertEqual(
                json.loads(schema_path.read_text(encoding="utf-8"))["benchmark_version"],
                "cohort-benchmark-v1",
            )

    def test_api_surface_builds_benchmark(self) -> None:
        server = create_server("127.0.0.1", 0, ".glio-cohort-benchmark-test")
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = server.server_address
            connection = HTTPConnection(host, port, timeout=20)
            connection.request("GET", "/v1/cohort/benchmark/schema")
            schema_response = connection.getresponse()
            self.assertEqual(schema_response.status, 200)
            self.assertEqual(
                json.loads(schema_response.read())["benchmark_version"],
                "cohort-benchmark-v1",
            )
            body = json.dumps(
                {
                    "dataset_id": "api-cohort",
                    "records": records(),
                    "config": {
                        "split": {
                            "strategy": "temporal",
                            "minimum_records_per_split": 1,
                        },
                        "calibration": {"minimum_records": 1},
                        "selective_risk": {"minimum_records": 1},
                        "transport": {"minimum_records_per_domain": 1},
                        "source_domain": "source",
                        "target_domains": ["target"],
                    },
                }
            ).encode()
            connection.request(
                "POST",
                "/v1/cohort/benchmark",
                body=body,
                headers={"Content-Type": "application/json", "Content-Length": str(len(body))},
            )
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            payload = json.loads(response.read())
            self.assertEqual(payload["state"], "accepted")
            connection.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
