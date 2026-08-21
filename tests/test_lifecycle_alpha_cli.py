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
                "claim_id": "claim-1",
                "edge_id": "edge-1",
                "state": "supported",
                "support": 0.8,
                "confidence": 0.9,
                "claim_type": "functional",
                "summary": "declared claim",
                "source_ids": ["source-1"],
                "source_versions": {"source-1": "v1"},
            }
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
            }
        ],
    }


class LifecycleAlphaCliTests(unittest.TestCase):
    def _write(self, root: Path, name: str, payload: object) -> Path:
        path = root / name
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_blinded_plan_and_adjudication_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._write(
                root,
                "observations.json",
                {
                    "observations": [
                        {
                            "observation_id": "obs-1",
                            "claim_id": "claim-1",
                            "edge_id": "edge-1",
                            "context_key": CONTEXT,
                            "evidence_digest": "sha256:evidence",
                            "source_ids": ["source-1"],
                        }
                    ]
                },
            )
            plan_output = root / "plan.json"
            self.assertEqual(
                main(
                    [
                        "plan-blinded-adjudication",
                        str(source),
                        "--context-key",
                        CONTEXT,
                        "--output",
                        str(plan_output),
                    ]
                ),
                0,
            )
            plan = json.loads(plan_output.read_text(encoding="utf-8"))
            case_id = plan["cases"][0]["case_id"]
            decisions = [
                {
                    "decision_id": "decision-1",
                    "case_id": case_id,
                    "reviewer_token": plan["reviewer_tokens"][0],
                    "verdict": "supports",
                    "confidence": 0.8,
                    "rationale": "supports",
                    "context_key": CONTEXT,
                },
                {
                    "decision_id": "decision-2",
                    "case_id": case_id,
                    "reviewer_token": plan["reviewer_tokens"][1],
                    "verdict": "supports",
                    "confidence": 0.8,
                    "rationale": "supports",
                    "context_key": CONTEXT,
                },
            ]
            adjudication_source = self._write(
                root,
                "adjudication.json",
                {"plan": plan, "decisions": decisions},
            )
            adjudication_output = root / "adjudication-output.json"
            self.assertEqual(
                main(
                    [
                        "adjudicate-blinded-evidence",
                        str(adjudication_source),
                        "--output",
                        str(adjudication_output),
                    ]
                ),
                0,
            )
            result = json.loads(adjudication_output.read_text(encoding="utf-8"))
            self.assertEqual(result["state"], "adjudicated")

    def test_review_release_and_delta_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            review_source = self._write(
                root,
                "review.json",
                {
                    "comments": [
                        {
                            "comment_id": "comment-1",
                            "target_id": "claim-1",
                            "author_role": "domain_expert",
                            "text": "retain context gate",
                        }
                    ],
                    "changes": [
                        {
                            "change_id": "change-1",
                            "target_id": "claim-1",
                            "actor_role": "domain_expert",
                            "before_hash": "sha256:before",
                            "after_hash": "sha256:after",
                            "rationale": "record gate",
                        }
                    ],
                },
            )
            review_output = root / "review-output.json"
            self.assertEqual(
                main(
                    [
                        "record-review-log",
                        str(review_source),
                        "--context-key",
                        CONTEXT,
                        "--output",
                        str(review_output),
                    ]
                ),
                0,
            )
            self.assertEqual(
                json.loads(review_output.read_text(encoding="utf-8"))["state"],
                "ready_for_review",
            )
            graph = graph_payload()
            release_source = self._write(
                root,
                "release.json",
                {
                    "graph": graph,
                    "gates": [
                        {
                            "gate_id": "gate-1",
                            "label": "citation coverage",
                            "passed": True,
                            "context_key": CONTEXT,
                            "evidence_hash": "sha256:gate",
                            "reason": "resolved",
                            "source_id": "audit",
                        }
                    ],
                },
            )
            release_output = root / "release-output.json"
            self.assertEqual(
                main(
                    [
                        "record-release-decision",
                        str(release_source),
                        "--requested-decision",
                        "approved",
                        "--required-role",
                        "domain_expert",
                        "--completed-role",
                        "domain_expert",
                        "--output",
                        str(release_output),
                    ]
                ),
                0,
            )
            self.assertEqual(
                json.loads(release_output.read_text(encoding="utf-8"))["state"],
                "approved",
            )
            delta_source = self._write(
                root,
                "delta.json",
                {"previous": graph, "current": graph | {"graph_version": 2}},
            )
            delta_output = root / "delta-output.json"
            self.assertEqual(
                main(
                    [
                        "detect-evidence-delta",
                        str(delta_source),
                        "--expected-context-key",
                        CONTEXT,
                        "--output",
                        str(delta_output),
                    ]
                ),
                0,
            )
            delta = json.loads(delta_output.read_text(encoding="utf-8"))
            self.assertEqual(delta["state"], "ready_for_review")
            self.assertFalse(delta["deltas"])


if __name__ == "__main__":
    unittest.main()
