from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main

CONTEXT = "GRCh38|glioma|adult|stem_like|core|unknown"


def evidence(evidence_id: str, source_id: str) -> dict[str, object]:
    return {
        "evidence_id": evidence_id,
        "mediator_kind": "sequence_to_element",
        "source_node": "variant:v1",
        "target_node": "element:enh-1",
        "context_key": CONTEXT,
        "support": 0.8,
        "uncertainty": 0.1,
        "source_id": source_id,
        "source_version": "v1",
        "sensitivity": 0.7,
    }


class CausalBetaCliTests(unittest.TestCase):
    def test_parse_and_evaluate_mediator_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "causal.json"
            parsed_output = root / "parsed.json"
            evaluated_output = root / "evaluated.json"
            source.write_text(
                json.dumps({"evidence": [evidence("e-1", "atlas-a"), evidence("e-2", "atlas-b")]}),
                encoding="utf-8",
            )
            self.assertEqual(
                main(
                    [
                        "parse-causal-evidence",
                        str(source),
                        "--source-id",
                        "causal-input",
                        "--output",
                        str(parsed_output),
                    ]
                ),
                0,
            )
            parsed = json.loads(parsed_output.read_text(encoding="utf-8"))
            self.assertEqual(len(parsed["evidence"]), 2)
            self.assertEqual(
                main(
                    [
                        "evaluate-sequence-element-mediator",
                        str(source),
                        "--source-node",
                        "variant:v1",
                        "--target-node",
                        "element:enh-1",
                        "--context-key",
                        CONTEXT,
                        "--model-id",
                        "seq-element-beta",
                        "--model-version",
                        "1",
                        "--output",
                        str(evaluated_output),
                    ]
                ),
                0,
            )
            evaluated = json.loads(evaluated_output.read_text(encoding="utf-8"))
            self.assertEqual(evaluated["state"], "supported")
            self.assertEqual(set(evaluated["source_ids"]), {"atlas-a", "atlas-b"})

    def test_element_gene_gene_state_and_counterfactual_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            element_gene = root / "element-gene.json"
            element_gene_output = root / "element-gene-output.json"
            element_gene.write_text(
                json.dumps(
                    {
                        "evidence": [
                            {
                                **evidence("eg-1", "contact-a"),
                                "mediator_kind": "element_to_gene",
                                "source_node": "element:enh-1",
                                "target_node": "gene:GENE1",
                            },
                            {
                                **evidence("eg-2", "contact-b"),
                                "mediator_kind": "element_to_gene",
                                "source_node": "element:enh-1",
                                "target_node": "gene:GENE1",
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                main(
                    [
                        "evaluate-element-gene-mediator",
                        str(element_gene),
                        "--source-node",
                        "element:enh-1",
                        "--target-node",
                        "gene:GENE1",
                        "--context-key",
                        CONTEXT,
                        "--model-id",
                        "element-gene-beta",
                        "--model-version",
                        "1",
                        "--output",
                        str(element_gene_output),
                    ]
                ),
                0,
            )
            self.assertEqual(
                json.loads(element_gene_output.read_text(encoding="utf-8"))["state"],
                "supported",
            )

            gene_state = root / "gene-state.json"
            gene_state_output = root / "gene-state-output.json"
            gene_state.write_text(
                json.dumps(
                    {
                        "evidence": [
                            {
                                **evidence("gs-1", "state-a"),
                                "mediator_kind": "gene_to_state",
                                "source_node": "gene:GENE1",
                                "target_node": "state:stem_like",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                main(
                    [
                        "evaluate-gene-state-mediator",
                        str(gene_state),
                        "--source-node",
                        "gene:GENE1",
                        "--target-node",
                        "state:stem_like",
                        "--context-key",
                        CONTEXT,
                        "--model-id",
                        "gene-state-beta",
                        "--model-version",
                        "1",
                        "--output",
                        str(gene_state_output),
                    ]
                ),
                0,
            )
            self.assertEqual(
                json.loads(gene_state_output.read_text(encoding="utf-8"))["state"],
                "partial",
            )

            counterfactual = root / "counterfactual.json"
            counterfactual_output = root / "counterfactual-output.json"
            counterfactual.write_text(
                json.dumps(
                    {
                        "observations": [
                            {
                                "observation_id": "ref",
                                "allele": "reference",
                                "state_id": "state:open",
                                "value": 0.2,
                                "uncertainty": 0.1,
                                "context_key": CONTEXT,
                                "source_id": "assay",
                                "source_version": "v1",
                            },
                            {
                                "observation_id": "alt",
                                "allele": "alternate",
                                "state_id": "state:open",
                                "value": 0.8,
                                "uncertainty": 0.1,
                                "context_key": CONTEXT,
                                "source_id": "assay",
                                "source_version": "v1",
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                main(
                    [
                        "simulate-counterfactual-allele-state",
                        str(counterfactual),
                        "--state-id",
                        "state:open",
                        "--context-key",
                        CONTEXT,
                        "--model-id",
                        "allele-state-beta",
                        "--model-version",
                        "1",
                        "--output",
                        str(counterfactual_output),
                    ]
                ),
                0,
            )
            simulated = json.loads(counterfactual_output.read_text(encoding="utf-8"))
            self.assertEqual(simulated["state"], "supported")
            self.assertAlmostEqual(simulated["delta_alternate_minus_reference"], 0.6)


if __name__ == "__main__":
    unittest.main()
