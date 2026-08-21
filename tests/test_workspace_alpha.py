from __future__ import annotations

import unittest

from glio_noncode.workspace_alpha import (
    CollaborationAction,
    CollaborationRole,
    ExperimentStatus,
    LaunchMode,
    NotebookRuntime,
    NotebookSDKLauncher,
    RoleBasedCollaborationEvaluator,
    ShareableSnapshotPublisher,
    ValidationExperimentBoardBuilder,
    WorkspaceAlphaState,
)

CONTEXT = "GRCh38|glioma|adult|stem_like|core|untreated"
OTHER_CONTEXT = "GRCh38|glioma|adult|differentiated|core|untreated"


class WorkspaceAlphaTests(unittest.TestCase):
    def test_validation_board_groups_cards_and_retains_dependencies(self) -> None:
        board = ValidationExperimentBoardBuilder().build(
            [
                {
                    "experiment_id": "exp-2",
                    "target_id": "target-1",
                    "title": "Reporter",
                    "assay_type": "reporter",
                    "status": "blocked",
                    "context_key": CONTEXT,
                    "priority": 5,
                    "owner": "team-a",
                    "dependencies": ["exp-1"],
                    "blockers": ["missing construct"],
                    "source_id": "planning",
                    "readout": "allele ratio",
                },
                {
                    "experiment_id": "exp-1",
                    "target_id": "target-1",
                    "title": "Guide screen",
                    "assay_type": "perturbation",
                    "status": "ready",
                    "context_key": CONTEXT,
                    "priority": 4,
                    "owner": "team-a",
                    "source_id": "planning",
                    "readout": "target expression",
                },
                {
                    "experiment_id": "foreign",
                    "target_id": "target-2",
                    "title": "Foreign context",
                    "assay_type": "screen",
                    "context_key": OTHER_CONTEXT,
                    "source_id": "planning",
                    "readout": "signal",
                },
            ],
            context_key=CONTEXT,
            board_id="board-1",
        )
        self.assertEqual(board.state, WorkspaceAlphaState.BLOCKED)
        self.assertEqual([item.experiment_id for item in board.cards], ["exp-1", "exp-2"])
        self.assertEqual(board.dependency_edges, (("exp-1", "exp-2"),))
        self.assertEqual(board.blocked_card_ids, ("exp-2",))
        self.assertEqual(len(board.issues), 1)
        self.assertEqual(board.issues[0].code, "context_mismatch")
        ready_column = next(
            item for item in board.columns if item.column_id == ExperimentStatus.READY.value
        )
        self.assertEqual(ready_column.card_ids, ("exp-1",))

    def test_notebook_launcher_is_declarative_and_network_is_review_required(self) -> None:
        plan = NotebookSDKLauncher().plan(
            [
                {
                    "request_id": "request-1",
                    "artifact_id": "notebook-1",
                    "runtime": NotebookRuntime.PYTHON.value,
                    "mode": LaunchMode.NOTEBOOK.value,
                    "context_key": CONTEXT,
                    "entrypoint": "analysis.main",
                    "parameters": {"window": 2000},
                    "resource_profile": "small",
                    "source_id": "workspace",
                },
                {
                    "request_id": "request-2",
                    "artifact_id": "sdk-1",
                    "runtime": NotebookRuntime.SDK.value,
                    "mode": LaunchMode.SDK.value,
                    "context_key": CONTEXT,
                    "entrypoint": "glio.run",
                    "parameters": {"limit": 10},
                    "resource_profile": "medium",
                    "allow_network": True,
                    "source_id": "workspace",
                },
            ],
            context_key=CONTEXT,
        )
        self.assertEqual(plan.state, WorkspaceAlphaState.REVIEW_REQUIRED)
        self.assertEqual(len(plan.launches), 2)
        self.assertTrue(all("--parameter-hash" in item.invocation for item in plan.launches))
        self.assertEqual(plan.launches[0].state, WorkspaceAlphaState.READY_FOR_REVIEW)
        self.assertEqual(plan.launches[1].state, WorkspaceAlphaState.REVIEW_REQUIRED)
        self.assertNotIn("analysis.main", plan.launches[0].invocation)

    def test_shareable_snapshot_verifies_and_detects_tampering(self) -> None:
        publisher = ShareableSnapshotPublisher()
        envelope = publisher.publish(
            {"workspace_id": "workspace-1", "records": ["claim-1"]},
            snapshot_id="snapshot-1",
            snapshot_type="workspace",
            context_key=CONTEXT,
            key_id="key-1",
            signing_secret="test-secret",
            audience=("review-team",),
        )
        verified = publisher.verify(envelope, signing_secret="test-secret")
        self.assertEqual(verified.state, WorkspaceAlphaState.VERIFIED)
        self.assertTrue(verified.signature_valid)
        self.assertTrue(verified.payload_hash_valid)
        tampered = envelope.to_dict()
        tampered["payload"] = {"workspace_id": "workspace-1", "records": ["changed"]}
        rejected = publisher.verify(tampered, signing_secret="test-secret")
        self.assertEqual(rejected.state, WorkspaceAlphaState.BLOCKED)
        self.assertFalse(rejected.payload_hash_valid)

    def test_role_based_collaboration_denies_unknown_actions_and_foreign_context(self) -> None:
        report = RoleBasedCollaborationEvaluator().evaluate(
            [
                {
                    "member_id": "reviewer-1",
                    "display_label": "Reviewer",
                    "role": CollaborationRole.REVIEWER.value,
                    "context_key": CONTEXT,
                    "source_id": "roster",
                },
                {
                    "member_id": "viewer-1",
                    "display_label": "Viewer",
                    "role": CollaborationRole.VIEWER.value,
                    "context_key": CONTEXT,
                    "source_id": "roster",
                },
            ],
            [
                {
                    "request_id": "access-1",
                    "member_id": "reviewer-1",
                    "action": CollaborationAction.APPROVE.value,
                    "target_id": "claim-1",
                    "context_key": CONTEXT,
                    "reason": "review claim",
                },
                {
                    "request_id": "access-2",
                    "member_id": "viewer-1",
                    "action": CollaborationAction.EDIT.value,
                    "target_id": "claim-1",
                    "context_key": CONTEXT,
                    "reason": "edit claim",
                },
                {
                    "request_id": "access-3",
                    "member_id": "reviewer-1",
                    "action": CollaborationAction.VIEW.value,
                    "target_id": "claim-1",
                    "context_key": OTHER_CONTEXT,
                    "reason": "foreign request",
                },
            ],
            workspace_id="workspace-1",
            context_key=CONTEXT,
        )
        self.assertEqual(report.state, WorkspaceAlphaState.OUT_OF_DOMAIN)
        self.assertTrue(report.decisions[0].allowed)
        self.assertFalse(report.decisions[1].allowed)
        self.assertEqual(report.decisions[2].state, WorkspaceAlphaState.OUT_OF_DOMAIN)


if __name__ == "__main__":
    unittest.main()
