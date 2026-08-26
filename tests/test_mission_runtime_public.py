from __future__ import annotations

import json
import tempfile
import unittest
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread

from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.mission_runtime import MissionRequest
from glio_noncode.mission_runtime_public import (
    MISSION_PLAN_PUBLIC_VERSION,
    MissionPlanPublicReceipt,
    build_public_mission_plan,
    mission_plan_public_capabilities,
    mission_plan_public_export_payloads,
    mission_plan_public_json,
    mission_plan_public_schema,
    mission_request_from_mapping,
    render_mission_plan_public_markdown,
)


def _contains_restricted_key(value: object) -> bool:
    restricted = {
        "agent",
        "agent_id",
        "agent_ids",
        "assistant",
        "author",
        "language",
        "model",
        "producer",
        "role_id",
        "tool_id",
        "tool_ids",
    }
    if isinstance(value, dict):
        return any(
            str(key).casefold() in restricted or _contains_restricted_key(item)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(_contains_restricted_key(item) for item in value)
    return False


class MissionRuntimePublicTests(unittest.TestCase):
    @staticmethod
    def _payload() -> dict[str, object]:
        return {
            "mission": {
                "mission_id": "mission-public",
                "project_id": "glio-noncode",
                "intended_use": "research hypothesis exploration",
                "requested_question": "Which bounded observations require review?",
                "allowed_data_scopes": ["synthetic", "public_reference"],
            },
            "requested_agent_ids": ["A02"],
            "workflow_id": "public-workflow",
        }

    def test_projection_is_deterministic_and_redacts_internal_routing(self) -> None:
        receipt = build_public_mission_plan(self._payload())
        self.assertEqual(receipt.version, MISSION_PLAN_PUBLIC_VERSION)
        self.assertEqual(receipt.state.value, "planned")
        self.assertEqual(receipt.selected_role_count, 2)
        self.assertGreater(receipt.selected_operation_count, 0)
        self.assertEqual(receipt.step_count, 8)
        payload = receipt.to_dict()
        self.assertFalse(_contains_restricted_key(payload), payload)
        self.assertNotIn("selected_agent_ids", payload)
        self.assertNotIn("selected_tool_ids", payload)
        self.assertEqual(MissionPlanPublicReceipt.from_mapping(payload).to_dict(), payload)
        self.assertEqual(json.loads(mission_plan_public_json(receipt)), payload)

    def test_custom_workflow_projects_resources_without_tool_metadata(self) -> None:
        payload = self._payload() | {
            "workflow_steps": [
                {
                    "step_id": "root",
                    "kind": "ingest",
                    "resource": {
                        "cpu": 2,
                        "memory_gb": 3,
                        "storage_gb": 4,
                        "max_seconds": 12,
                    },
                    "output_contract": "case_manifest",
                },
                {
                    "step_id": "review",
                    "kind": "review",
                    "depends_on": ["root"],
                    "optional": True,
                    "output_contract": "reviewable_snapshot",
                },
            ]
        }
        receipt = build_public_mission_plan(payload)
        self.assertEqual(receipt.workflow_id, "public-workflow")
        self.assertEqual([item.step_id for item in receipt.steps], ["root", "review"])
        self.assertEqual(receipt.steps[0].resource["cpu"], 2.0)
        self.assertTrue(receipt.steps[1].optional)
        self.assertEqual(receipt.total_cpu, 3.0)

    def test_empty_request_abstains_without_hidden_work(self) -> None:
        receipt = build_public_mission_plan(
            {
                "mission": self._payload()["mission"],
                "requested_agent_ids": [],
            }
        )
        self.assertTrue(receipt.accepted)
        self.assertTrue(receipt.abstained)
        self.assertEqual(receipt.state.value, "abstained")
        self.assertEqual(receipt.step_count, 0)
        self.assertIsNone(receipt.workflow_id)

    def test_request_parser_rejects_invalid_workflow_and_duplicate_inputs(self) -> None:
        with self.assertRaises(ValidationError):
            mission_request_from_mapping(self._payload() | {"requested_agent_ids": ["A02", "A02"]})
        with self.assertRaises(ValidationError):
            mission_request_from_mapping(
                self._payload()
                | {
                    "workflow_steps": [
                        {"step_id": "cycle-a", "kind": "review", "depends_on": ["cycle-b"]},
                        {"step_id": "cycle-b", "kind": "review", "depends_on": ["cycle-a"]},
                    ]
                }
            )
        request = mission_request_from_mapping(self._payload())
        self.assertIsInstance(request, MissionRequest)
        self.assertEqual(request.workflow_id, "public-workflow")

    def test_hydration_and_tamper_detection_reconcile_address(self) -> None:
        receipt = build_public_mission_plan(self._payload())
        hydrated = MissionPlanPublicReceipt.from_mapping(receipt.to_dict())
        self.assertEqual(hydrated.content_address, receipt.content_address)
        with self.assertRaises(ValidationError):
            MissionPlanPublicReceipt.from_mapping(
                receipt.to_dict() | {"selected_role_count": receipt.selected_role_count + 1}
            )
        with self.assertRaises(ValidationError):
            MissionPlanPublicReceipt.from_mapping(
                receipt.to_dict() | {"selected_agent_ids": ["must-not-publish"]}
            )
        with self.assertRaises(ValidationError):
            MissionPlanPublicReceipt.from_mapping(receipt.to_dict() | {"unexpected": True})
        with self.assertRaises(ValidationError):
            MissionPlanPublicReceipt.from_mapping(
                receipt.to_dict()
                | {"steps": [{"step_id": "x", "kind": "ingest", "resource": {"agent_id": "x"}}]}
            )

    def test_exports_are_deterministic_and_boundary_safe(self) -> None:
        receipt = build_public_mission_plan(self._payload())
        exports = mission_plan_public_export_payloads(receipt)
        self.assertEqual(
            set(exports), {"mission-plan.json", "mission-plan.md", "mission-plan-steps.csv"}
        )
        self.assertEqual(exports["mission-plan.json"], mission_plan_public_json(receipt))
        self.assertIn("internal routing metadata is omitted", exports["mission-plan.md"])
        self.assertIn("step_id", exports["mission-plan-steps.csv"].splitlines()[0])
        self.assertEqual(exports["mission-plan.md"], render_mission_plan_public_markdown(receipt))
        self.assertFalse(_contains_restricted_key(exports))
        self.assertEqual(mission_plan_public_schema()["contract_version"], MISSION_PLAN_PUBLIC_VERSION)
        self.assertTrue(mission_plan_public_capabilities()["role_identifier_redaction"])

    def test_cli_surface_emits_public_receipt_and_contract_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "mission.json"
            source.write_text(json.dumps(self._payload()), encoding="utf-8")
            output = root / "mission-output.json"
            self.assertEqual(
                main(["mission-plan", str(source), "--output", str(output)]),
                0,
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["version"], MISSION_PLAN_PUBLIC_VERSION)
            self.assertNotIn("selected_agent_ids", payload)
            markdown = root / "mission.md"
            self.assertEqual(
                main(
                    [
                        "mission-plan",
                        str(source),
                        "--format",
                        "markdown",
                        "--output",
                        str(markdown),
                    ]
                ),
                0,
            )
            self.assertIn("# Mission plan", markdown.read_text(encoding="utf-8"))
            schema = root / "schema.json"
            capabilities = root / "capabilities.json"
            self.assertEqual(main(["mission-plan-schema", "--output", str(schema)]), 0)
            self.assertEqual(main(["mission-plan-capabilities", "--output", str(capabilities)]), 0)
            self.assertEqual(json.loads(schema.read_text(encoding="utf-8"))["contract_version"], MISSION_PLAN_PUBLIC_VERSION)
            self.assertTrue(json.loads(capabilities.read_text(encoding="utf-8"))["api_surface"])

    def test_http_surface_emits_public_receipt_and_rejects_bad_input(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            server = create_server("127.0.0.1", 0, directory)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                connection = HTTPConnection(host, port, timeout=30)
                body = json.dumps(self._payload()).encode("utf-8")
                connection.request(
                    "POST",
                    "/v1/mission/plan",
                    body=body,
                    headers={"Content-Type": "application/json", "Content-Length": str(len(body))},
                )
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                payload = json.loads(response.read())
                self.assertEqual(payload["version"], MISSION_PLAN_PUBLIC_VERSION)
                self.assertNotIn("selected_agent_ids", payload)
                connection.request("GET", "/v1/mission/plan/schema")
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertEqual(json.loads(response.read())["contract_version"], MISSION_PLAN_PUBLIC_VERSION)
                connection.request("GET", "/v1/mission/plan/capabilities")
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertTrue(json.loads(response.read())["public_boundary_validation"])
                bad_body = b"[]"
                connection.request(
                    "POST",
                    "/v1/mission/plan",
                    body=bad_body,
                    headers={"Content-Type": "application/json", "Content-Length": str(len(bad_body))},
                )
                response = connection.getresponse()
                self.assertEqual(response.status, 400)
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
