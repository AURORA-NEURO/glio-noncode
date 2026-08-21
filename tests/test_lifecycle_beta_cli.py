from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main

CONTEXT = "GRCh38|glioma|adult|stem_like|core|untreated"


def graph_payload() -> dict[str, object]:
    return {
        "graph_id": "cli-graph",
        "context_key": CONTEXT,
        "claims": [
            {
                "claim_id": "positive",
                "edge_id": "edge-1",
                "state": "supported",
                "support": 0.8,
                "confidence": 0.8,
                "claim_type": "functional",
                "summary": "positive claim",
                "source_ids": ["source-1"],
                "source_versions": {"source-1": "v1"},
                "attributes": {"claim_value": "increases"},
            },
            {
                "claim_id": "negative",
                "edge_id": "edge-1",
                "state": "measured_negative",
                "support": 0.2,
                "confidence": 0.7,
                "claim_type": "functional",
                "summary": "negative claim",
                "source_ids": ["source-2"],
                "source_versions": {"source-2": "v1"},
                "attributes": {"claim_value": "decreases"},
            },
        ],
        "citations": [
            {
                "citation_id": "citation-1",
                "source_id": "source-1",
                "source_uri": "https://example.test/source-1",
                "title": "Source 1",
                "version": "v1",
                "citation_text": "Source one",
                "retrieved_at": "2026-08-21T00:00:00+00:00",
            },
            {
                "citation_id": "citation-2",
                "source_id": "source-2",
                "source_uri": "https://example.test/source-2",
                "title": "Source 2",
                "version": "v1",
                "citation_text": "Source two",
                "retrieved_at": "2026-08-21T00:00:00+00:00",
            },
        ],
    }


class LifecycleBetaCliTests(unittest.TestCase):
    def test_tier_and_uncertainty_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tier_source = root / "tiers.json"
            tier_output = root / "tiers-output.json"
            tier_source.write_text(
                json.dumps(
                    {
                        "observations": [
                            {
                                "observation_id": "tier-1",
                                "claim_id": "claim-1",
                                "edge_id": "edge-1",
                                "context_key": CONTEXT,
                                "tier": "direct_perturbation",
                                "direction": "supports",
                                "confidence": 0.8,
                                "source_id": "perturbation",
                                "rationale": "declared direct perturbation",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                main(
                    [
                        "adjudicate-evidence-tier",
                        str(tier_source),
                        "--context-key",
                        CONTEXT,
                        "--output",
                        str(tier_output),
                    ]
                ),
                0,
            )
            tier = json.loads(tier_output.read_text(encoding="utf-8"))
            self.assertEqual(tier["state"], "supported")
            self.assertEqual(tier["decisions"][0]["highest_tier"], "direct_perturbation")

            uncertainty_source = root / "uncertainty.json"
            uncertainty_output = root / "uncertainty-output.json"
            uncertainty_source.write_text(
                json.dumps(
                    {
                        "entries": [
                            {
                                "observation_id": "u-1",
                                "claim_id": "claim-1",
                                "edge_id": "edge-1",
                                "context_key": CONTEXT,
                                "dimension": "transport",
                                "value": 0.8,
                                "source_id": "audit",
                                "rationale": "context transport",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                main(
                    [
                        "build-uncertainty-ledger",
                        str(uncertainty_source),
                        "--context-key",
                        CONTEXT,
                        "--output",
                        str(uncertainty_output),
                    ]
                ),
                0,
            )
            uncertainty = json.loads(uncertainty_output.read_text(encoding="utf-8"))
            self.assertEqual(uncertainty["claims"][0]["top_dimension"], "transport")

    def test_lineage_and_reviewer_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "graph.json"
            source.write_text(json.dumps(graph_payload()), encoding="utf-8")
            lineage_output = root / "lineage.json"
            self.assertEqual(
                main(
                    [
                        "view-provenance-lineage",
                        str(source),
                        "--claim-id",
                        "positive",
                        "--output",
                        str(lineage_output),
                    ]
                ),
                0,
            )
            lineage = json.loads(lineage_output.read_text(encoding="utf-8"))
            self.assertEqual(lineage["state"], "review_required")
            self.assertIn("source", {item["relation"] for item in lineage["edges"]})
            self.assertIn("citation", {item["relation"] for item in lineage["edges"]})

            reviewer_source = root / "review.json"
            payload = graph_payload()
            payload["uncertainty"] = [
                {
                    "observation_id": "u-1",
                    "claim_id": "positive",
                    "edge_id": "edge-1",
                    "context_key": CONTEXT,
                    "dimension": "measurement",
                    "value": 0.7,
                    "source_id": "audit",
                    "rationale": "replicate spread",
                }
            ]
            reviewer_source.write_text(json.dumps(payload), encoding="utf-8")
            reviewer_output = root / "review-output.json"
            self.assertEqual(
                main(
                    [
                        "route-reviewers",
                        str(reviewer_source),
                        "--roles",
                        "data_provenance",
                        "domain_expert",
                        "--output",
                        str(reviewer_output),
                    ]
                ),
                0,
            )
            reviewer = json.loads(reviewer_output.read_text(encoding="utf-8"))
            self.assertEqual(reviewer["state"], "contradictory")
            self.assertEqual(len(reviewer["assignments"]), 2)
            role_values = set(reviewer["assignments"][0]["roles"])
            self.assertIn("statistical_review", role_values)


if __name__ == "__main__":
    unittest.main()
