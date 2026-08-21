from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main


class ControlBetaCliTests(unittest.TestCase):
    def _run(
        self,
        root: Path,
        name: str,
        payload: dict[str, object],
        *args: str,
    ) -> dict[str, object]:
        source = root / f"{name}.json"
        output = root / f"{name}-output.json"
        source.write_text(json.dumps(payload), encoding="utf-8")
        self.assertEqual(main([*args, str(source), "--output", str(output)]), 0)
        return json.loads(output.read_text(encoding="utf-8"))

    def test_policy_audit_and_budget_schedule_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            policy = self._run(
                root,
                "policy",
                {
                    "request": {
                        "request_id": "request-cli",
                        "agent_id": "A08",
                        "tool_id": "A08.publish",
                        "input_payload": {"case_hash": "sha256:case", "question": "bounded"},
                        "mission": {
                            "mission_id": "mission-cli",
                            "project_id": "glio-noncode",
                            "intended_use": "research-only audit",
                            "requested_question": "Which bounded path is allowed?",
                            "claim_ceiling": "hypothesis",
                        },
                        "provenance": {"input_hashes": ["sha256:case"]},
                    }
                },
                "audit-policy-claim",
            )
            self.assertEqual(policy["state"], "supported")
            self.assertTrue(policy["allowed"])

            schedule = self._run(
                root,
                "schedule",
                {
                    "items": [
                        {"item_id": "root", "priority": 1, "resource": {"max_seconds": 2}},
                        {
                            "item_id": "child",
                            "priority": 5,
                            "depends_on": ["root"],
                            "resource": {"max_seconds": 3},
                        },
                    ]
                },
                "schedule-budget",
                "--max-seconds",
                "10",
            )
            self.assertEqual(schedule["state"], "ready")
            self.assertEqual(schedule["admitted_item_ids"], ["root", "child"])

    def test_fallback_and_review_queue_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fallback = self._run(
                root,
                "fallback",
                {
                    "request": {
                        "request_id": "fallback-cli",
                        "failed_operation_id": "primary",
                        "failure_code": "source_unavailable",
                        "retryable": True,
                        "available_inputs": ["case"],
                        "requested_output_contract": "evidence",
                        "remaining_cost_units": 5,
                    },
                    "candidates": [
                        {
                            "candidate_id": "alternate",
                            "operation_id": "secondary",
                            "required_inputs": ["case"],
                            "output_contract": "evidence",
                        }
                    ],
                },
                "route-fallback",
            )
            self.assertEqual(fallback["state"], "selected")
            self.assertEqual(fallback["selected_candidate_id"], "alternate")

            review = self._run(
                root,
                "review",
                {
                    "items": [
                        {
                            "item_id": "review-1",
                            "request_id": "request-1",
                            "execution_role_id": "role-1",
                            "tool_id": "tool-1",
                            "state": "abstained",
                            "reasons": ["missing_input"],
                            "blockers": ["abstention"],
                            "priority": 90,
                            "requires_review": True,
                        }
                    ]
                },
                "queue-human-review",
            )
            self.assertEqual(review["state"], "blocked")
            self.assertEqual(review["assignments"][0]["item_id"], "review-1")
            self.assertTrue(review["assignments"][0]["blocked"])


if __name__ == "__main__":
    unittest.main()
