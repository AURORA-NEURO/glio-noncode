from __future__ import annotations

import unittest

from glio_noncode.control_plane import (
    ClaimCeiling,
    InvocationRequest,
    InvocationState,
    MissionContext,
    ProvenanceContext,
)
from glio_noncode.control_plane_app import ControlPlaneApplication


def _request(
    tool_id: str,
    payload: dict[str, object],
    request_id: str,
    *,
    release: bool = False,
) -> InvocationRequest:
    mission = MissionContext(
        mission_id="mission-app-test",
        project_id="project-app-test",
        intended_use="research-only control-plane integration",
        requested_question="Which bounded workflow should run?",
        claim_ceiling=(ClaimCeiling.RESEARCH_RELEASE if release else ClaimCeiling.HYPOTHESIS),
    )
    return InvocationRequest(
        request_id=request_id,
        mission=mission,
        agent_id=tool_id.split(".")[0],
        tool_id=tool_id,
        input_payload=payload,
        provenance=ProvenanceContext(("sha256:input",), reference_build="GRCh38"),
        idempotency_key=f"idem-{request_id}",
    )


class ControlPlaneApplicationTests(unittest.TestCase):
    def test_core_bindings_execute_real_intake_and_identity_handlers(self) -> None:
        app = ControlPlaneApplication()
        self.assertEqual(app.manifest()["binding_count"], 6)
        vcf = "\n".join(
            (
                "##fileformat=VCFv4.3",
                "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO",
                "7\t100\tv1\tA\tT\t.\tPASS\t.",
            )
        )
        intake = app.executor.execute(
            _request(
                "A07.publish",
                {"text": vcf, "source_id": "control-plane-vcf", "input_format": "vcf"},
                "intake-1",
            )
        )
        self.assertEqual(intake.state, InvocationState.COMPLETED)
        self.assertEqual(intake.response.state.value, "supported")
        identity = app.executor.execute(
            _request(
                "A08.publish",
                {"notation": "7:100:A>T", "variant_id": "v1"},
                "identity-1",
            )
        )
        self.assertEqual(identity.state, InvocationState.COMPLETED)
        self.assertEqual(identity.response.state.value, "supported")

    def test_power_drift_and_human_review_bindings_are_typed(self) -> None:
        app = ControlPlaneApplication()
        power = app.executor.execute(
            _request("A41.publish", {"effect_size": 0.2, "target_power": 0.8}, "power-1")
        )
        self.assertEqual(power.state, InvocationState.COMPLETED)
        drift = app.executor.execute(
            _request(
                "A47.publish",
                {
                    "baseline": {"unsupported_claim_fraction": 0.1},
                    "current": {"unsupported_claim_fraction": 0.8},
                },
                "drift-1",
            )
        )
        self.assertEqual(drift.state, InvocationState.COMPLETED)
        review = app.executor.execute(_request("A45.publish", {}, "review-1", release=True))
        self.assertEqual(review.state, InvocationState.ABSTAINED)
        self.assertEqual(review.response.reason_code, "human_adjudication_required")


if __name__ == "__main__":
    unittest.main()
