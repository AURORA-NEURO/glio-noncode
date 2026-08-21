from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main

CONTEXT = "GRCh38|glioma|adult|stem_like|core|untreated"


class WorkspaceBetaCliTests(unittest.TestCase):
    def _run(
        self, root: Path, name: str, payload: dict[str, object], *args: str
    ) -> dict[str, object]:
        source = root / f"{name}.json"
        output = root / f"{name}-output.json"
        source.write_text(json.dumps(payload), encoding="utf-8")
        self.assertEqual(main([*args, str(source), "--output", str(output)]), 0)
        return json.loads(output.read_text(encoding="utf-8"))

    def test_topology_and_causal_commands_write_deep_views(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            topology = self._run(
                root,
                "topology",
                {
                    "loops": [
                        {
                            "feature_id": "loop-1",
                            "feature_kind": "loop",
                            "chromosome_a": "7",
                            "start_a": 100,
                            "end_a": 120,
                            "chromosome_b": "7",
                            "start_b": 1000,
                            "end_b": 1020,
                            "signal": 7,
                            "context_key": CONTEXT,
                            "source_id": "hic",
                            "source_version": "v1",
                        }
                    ],
                    "contacts": [],
                },
                "view-topology",
                "--context-key",
                CONTEXT,
            )
            self.assertEqual(topology["state"], "supported")
            self.assertEqual(len(topology["edges"]), 1)

            causal = self._run(
                root,
                "causal",
                {
                    "results": [
                        {
                            "mediator_kind": "sequence_to_element",
                            "source_node": "variant-1",
                            "target_node": "element-1",
                            "context_key": CONTEXT,
                            "state": "supported",
                            "support": 0.8,
                            "uncertainty": 0.1,
                            "evidence_ids": ["e-1"],
                            "source_ids": ["seq"],
                            "source_versions": ["v1"],
                            "reason": "sequence evidence",
                        },
                        {
                            "mediator_kind": "element_to_gene",
                            "source_node": "element-1",
                            "target_node": "gene-1",
                            "context_key": CONTEXT,
                            "state": "supported",
                            "support": 0.7,
                            "uncertainty": 0.2,
                            "evidence_ids": ["e-2"],
                            "source_ids": ["contact"],
                            "source_versions": ["v1"],
                            "reason": "contact evidence",
                        },
                        {
                            "mediator_kind": "gene_to_state",
                            "source_node": "gene-1",
                            "target_node": "state-1",
                            "context_key": CONTEXT,
                            "state": "supported",
                            "support": 0.6,
                            "uncertainty": 0.2,
                            "evidence_ids": ["e-3"],
                            "source_ids": ["state"],
                            "source_versions": ["v1"],
                            "reason": "state evidence",
                        },
                    ]
                },
                "explore-causal-chain",
                "--context-key",
                CONTEXT,
            )
            self.assertEqual(causal["state"], "complete")
            self.assertEqual(len(causal["edges"]), 3)

    def test_posterior_and_evidence_table_commands_preserve_filters(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            posterior = self._run(
                root,
                "posterior",
                {
                    "posterior": {
                        "hypothesis_id": "h-1",
                        "state": "supported",
                        "declared_prior": 0.2,
                        "evidence_support": 0.7,
                        "posterior_proxy": 0.6,
                    },
                    "components": [
                        {
                            "component_id": "a",
                            "label": "a",
                            "contribution": 0.4,
                            "context_key": CONTEXT,
                        },
                        {
                            "component_id": "b",
                            "label": "b",
                            "contribution": 0.3,
                            "context_key": CONTEXT,
                        },
                    ],
                },
                "view-posterior-decomposition",
                "--context-key",
                CONTEXT,
            )
            self.assertEqual(posterior["residual"], 0.0)
            self.assertEqual(posterior["state"], "supported")

            workspace = {
                "workspace_id": "workspace-cli",
                "kind": "case",
                "context_key": CONTEXT,
                "state": "partial",
                "warnings": [],
                "records": [
                    {
                        "record_id": "e-1",
                        "record_type": "evidence",
                        "label": "sequence claim",
                        "context_key": CONTEXT,
                        "state": "supported",
                        "source_ids": ["source-a"],
                        "tags": ["sequence", "tier-1"],
                        "fields": {"channel": "sequence", "tier": "tier-1", "confidence": 0.9},
                        "searchable_text": "sequence claim",
                    },
                    {
                        "record_id": "e-2",
                        "record_type": "evidence",
                        "label": "topology claim",
                        "context_key": CONTEXT,
                        "state": "partial",
                        "source_ids": ["source-b"],
                        "tags": ["topology", "tier-2"],
                        "fields": {"channel": "topology", "tier": "tier-2", "confidence": 0.4},
                        "searchable_text": "topology claim",
                    },
                ],
                "sections": [
                    {
                        "section_id": "evidence",
                        "title": "Evidence",
                        "record_types": ["evidence"],
                        "order": 0,
                        "accessible_label": "Evidence",
                        "description": "Evidence records",
                    }
                ],
            }
            table = self._run(
                root,
                "table",
                workspace,
                "filter-evidence-table",
                "--channel",
                "sequence",
                "--min-confidence",
                "0.8",
            )
            self.assertEqual(table["total_matches"], 1)
            self.assertEqual(table["rows"][0]["record_id"], "e-1")


if __name__ == "__main__":
    unittest.main()
