from __future__ import annotations

import copy
import json
import tempfile
import unittest
from dataclasses import replace

from glio_noncode.assessments import (
    RUN_ASSESSMENT_VERSION,
    VerifiedRunAssessment,
    assessment_capabilities,
    build_run_assessment,
)
from glio_noncode.errors import ValidationError
from glio_noncode.models import ReviewDecision, ReviewState
from glio_noncode.runtime import CaseRuntime, VerifiedRunSnapshot
from glio_noncode.serialization import canonical_json, content_hash
from glio_noncode.storage import MAX_RUN_HISTORY_ENTRIES

from .helpers import fixture_manifest


class VerifiedRunAssessmentTests(unittest.TestCase):
    def test_build_round_trip_and_verify_close_every_derived_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            dossier = runtime.evaluate(fixture_manifest())

            assessment = build_run_assessment(
                runtime,
                dossier.run_id,
                audience="public",
                format="markdown",
            )
            reopened = VerifiedRunAssessment.from_dict(assessment.to_dict())

            self.assertEqual(reopened, assessment)
            self.assertTrue(assessment.verify_without_rebuild(runtime))
            self.assertTrue(assessment.verify(runtime))
            self.assertEqual(assessment.assessment_version, RUN_ASSESSMENT_VERSION)
            self.assertEqual(assessment.dossier_address, dossier.content_address)
            self.assertEqual(assessment.quality_report.dossier_address, dossier.content_address)
            self.assertEqual(assessment.dossier_report.audience, "public")
            self.assertEqual(assessment.rendered_report.format, "markdown")
            self.assertTrue(assessment.rendered_report.payload.startswith("# Public"))

    def test_tampering_and_a_different_snapshot_fail_closed(self) -> None:
        with (
            tempfile.TemporaryDirectory() as first_directory,
            tempfile.TemporaryDirectory() as second_directory,
        ):
            first_runtime = CaseRuntime(first_directory)
            first = first_runtime.evaluate(fixture_manifest())
            assessment = build_run_assessment(first_runtime, first.run_id)
            raw = copy.deepcopy(assessment.to_dict())
            raw["event_address"] = "sha256:" + "0" * 64
            with self.assertRaisesRegex(ValidationError, "content_address"):
                VerifiedRunAssessment.from_dict(raw)

            second_manifest = replace(fixture_manifest(), case_id="case-assessment-second")
            second_runtime = CaseRuntime(second_directory)
            second_runtime.evaluate(second_manifest)
            self.assertFalse(assessment.verify_without_rebuild(second_runtime))

    def test_capabilities_are_deterministic_and_defaults_are_public_json(self) -> None:
        first = assessment_capabilities()
        second = assessment_capabilities()
        self.assertEqual(first, second)
        self.assertEqual(first["assessment_version"], RUN_ASSESSMENT_VERSION)
        self.assertEqual((first["default_audience"], first["default_format"]), ("public", "json"))
        self.assertEqual(
            first["history_authentication"],
            {
                "scheme": "snapshot-predecessor-v1",
                "current_snapshot_supported": True,
                "historical_snapshot_requires_successor_binding": True,
                "retained_modern_suffix_validated": True,
                "unbound_legacy_history_supported": False,
                "complete_index_rollback_requires_external_anchor": True,
            },
        )

    def test_builder_rejects_a_snapshot_outside_the_runtime_verification_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            dossier = runtime.evaluate(fixture_manifest())
            snapshot = runtime.load_run_snapshot(dossier.run_id)

            with self.assertRaisesRegex(ValidationError, "exact CaseRuntime"):
                build_run_assessment(snapshot, dossier.run_id)  # type: ignore[arg-type]

    def test_verifiers_revalidate_the_assessment_envelope_itself(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            dossier = runtime.evaluate(fixture_manifest())
            assessment = build_run_assessment(runtime, dossier.run_id)

            object.__setattr__(assessment, "assessment_version", "forged-version")

            self.assertFalse(assessment.verify(runtime))
            self.assertFalse(assessment.verify_without_rebuild(runtime))

    def test_assessment_rejects_instance_level_runtime_method_substitution(self) -> None:
        with (
            tempfile.TemporaryDirectory() as source_directory,
            tempfile.TemporaryDirectory() as empty_directory,
        ):
            source_runtime = CaseRuntime(source_directory)
            dossier = source_runtime.evaluate(fixture_manifest())
            snapshot = source_runtime.load_run_snapshot(dossier.run_id)
            assessment = build_run_assessment(source_runtime, dossier.run_id)
            empty_runtime = CaseRuntime(empty_directory)
            empty_runtime.__dict__["load_run_snapshot"] = lambda run_id: snapshot
            empty_runtime.__dict__["load_run_snapshot_at"] = (
                lambda run_id, **kwargs: snapshot
            )

            with self.assertRaisesRegex(ValidationError, "instance method overrides"):
                build_run_assessment(empty_runtime, dossier.run_id)
            self.assertFalse(assessment.verify(empty_runtime))
            self.assertFalse(assessment.verify_without_rebuild(empty_runtime))

            deeper_runtime = CaseRuntime(empty_directory)
            deeper_runtime.__dict__["get_run"] = (
                lambda run_id: snapshot.run_record_dict()
            )
            deeper_runtime.__dict__["_load_run_snapshot_record"] = (
                lambda run_id, run_record: snapshot
            )
            with self.assertRaisesRegex(ValidationError, "instance method overrides"):
                build_run_assessment(deeper_runtime, dossier.run_id)
            self.assertFalse(assessment.verify(deeper_runtime))
            self.assertFalse(assessment.verify_without_rebuild(deeper_runtime))

    def test_assessment_constructor_only_treats_empty_string_as_missing_address(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            dossier = runtime.evaluate(fixture_manifest())
            assessment = build_run_assessment(runtime, dossier.run_id)
            for invalid in (None, False, 0):
                with self.subTest(invalid=invalid), self.assertRaises(ValidationError):
                    replace(assessment, content_address=invalid)  # type: ignore[arg-type]

    def test_assessment_remains_verifiable_after_append_only_run_progression(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            draft = runtime.evaluate(fixture_manifest())
            draft_assessment = build_run_assessment(runtime, draft.run_id)
            reviewed = runtime.review(
                draft,
                ReviewDecision(
                    review_id="assessment-history-review",
                    case_id=draft.case_id,
                    reviewer="assessment-reviewer",
                    state=ReviewState.ACCEPTED,
                    reviewed_hypothesis_ids=tuple(
                        item.hypothesis_id for item in draft.hypotheses
                    ),
                    rationale="Reviewed every hypothesis and evidence claim.",
                    checked_claim_ids=tuple(item.evidence_id for item in draft.evidence),
                ),
            )
            current_assessment = build_run_assessment(runtime, reviewed.run_id)

            self.assertTrue(draft_assessment.verify(runtime))
            self.assertTrue(draft_assessment.verify_without_rebuild(runtime))
            self.assertTrue(current_assessment.verify(runtime))
            self.assertNotEqual(
                draft_assessment.dossier_address,
                current_assessment.dossier_address,
            )
            with self.assertRaisesRegex(ValidationError, "not a paired snapshot"):
                runtime.load_run_snapshot_at(
                    draft.run_id,
                    event_address=draft_assessment.event_address,
                    dossier_address=current_assessment.dossier_address,
                )

    def test_supported_legacy_history_is_right_aligned_across_progression(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            draft = runtime.evaluate(fixture_manifest())
            runtime.assign_review(
                draft.run_id,
                assignment_id="assessment-legacy-assignment-one",
                reviewer="assessment-reviewer-one",
            )
            path = runtime.store.runs / f"{draft.run_id}.json"
            legacy = json.loads(path.read_text(encoding="utf-8"))
            legacy.pop("event_history")
            path.write_text(canonical_json(legacy), encoding="utf-8")

            legacy_assessment = build_run_assessment(runtime, draft.run_id)
            self.assertTrue(legacy_assessment.verify(runtime))
            self.assertTrue(legacy_assessment.verify_without_rebuild(runtime))

            runtime.assign_review(
                draft.run_id,
                assignment_id="assessment-legacy-assignment-two",
                reviewer="assessment-reviewer-two",
            )
            progressed = runtime.get_run(draft.run_id)
            self.assertEqual(len(progressed["event_history"]), 2)
            self.assertEqual(len(progressed["dossier_history"]), 3)
            self.assertTrue(legacy_assessment.verify(runtime))
            self.assertTrue(legacy_assessment.verify_without_rebuild(runtime))

    def test_unbound_legacy_historical_snapshot_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            draft = runtime.evaluate(fixture_manifest())
            draft_assessment = build_run_assessment(runtime, draft.run_id)
            snapshot = runtime.load_run_snapshot(draft.run_id)
            legacy_log = snapshot.event_log
            assignment_body = {
                "assignment_id": "assessment-unbound-legacy-transition",
                "run_id": draft.run_id,
                "case_id": draft.case_id,
                "reviewer": "legacy-reviewer",
                "queue_id": "legacy-queue",
                "due_at": "",
                "note": "Canonical assignment from before predecessor bindings.",
                "created_at": "2026-09-01T12:00:00+00:00",
            }
            legacy_log.append(
                "review_assigned",
                assignment_body
                | {
                    "content_address": content_hash(
                        assignment_body,
                        prefix="review-assignment",
                    )
                },
                event_id=assignment_body["assignment_id"],
            )
            legacy_current = runtime._readdress(
                replace(draft, event_head=legacy_log.head)
            )
            runtime._persist(
                None,
                legacy_log,
                legacy_current,
                draft.input_address,
                expected_run=snapshot.run_record_dict(),
            )

            self.assertEqual(
                runtime.load_run_snapshot(draft.run_id).dossier,
                legacy_current,
            )
            with self.assertRaisesRegex(ValidationError, "no authenticated successor"):
                runtime.load_run_snapshot_at(
                    draft.run_id,
                    event_address=draft_assessment.event_address,
                    dossier_address=draft_assessment.dossier_address,
                )
            self.assertFalse(draft_assessment.verify(runtime))
            self.assertFalse(draft_assessment.verify_without_rebuild(runtime))

    def test_historical_loading_cannot_hide_a_rewound_current_pointer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            draft = runtime.evaluate(fixture_manifest())
            runtime.assign_review(
                draft.run_id,
                assignment_id="assessment-rewind-assignment",
                reviewer="assessment-reviewer",
            )
            path = runtime.store.runs / f"{draft.run_id}.json"
            rewound = json.loads(path.read_text(encoding="utf-8"))
            old_event = rewound["event_history"][0]
            old_dossier = rewound["dossier_history"][0]
            rewound["event_address"] = old_event
            rewound["dossier_address"] = old_dossier
            path.write_text(canonical_json(rewound), encoding="utf-8")

            with self.assertRaisesRegex(ValidationError, "current-ended"):
                runtime.load_run_snapshot(draft.run_id)
            with self.assertRaisesRegex(ValidationError, "current-ended"):
                runtime.load_run_snapshot_at(
                    draft.run_id,
                    event_address=old_event,
                    dossier_address=old_dossier,
                )

    def test_historical_loading_rejects_a_spliced_divergent_branch(self) -> None:
        with (
            tempfile.TemporaryDirectory() as first_directory,
            tempfile.TemporaryDirectory() as second_directory,
        ):
            first_runtime = CaseRuntime(first_directory)
            baseline = first_runtime.evaluate(fixture_manifest())
            second_runtime = CaseRuntime(second_directory)
            second_runtime.evaluate(fixture_manifest())
            first_runtime.assign_review(
                baseline.run_id,
                assignment_id="assessment-branch-a",
                reviewer="reviewer-a",
            )
            second_runtime.assign_review(
                baseline.run_id,
                assignment_id="assessment-branch-b",
                reviewer="reviewer-b",
            )
            foreign_assessment = build_run_assessment(second_runtime, baseline.run_id)
            first_record = first_runtime.get_run(baseline.run_id)
            second_record = second_runtime.get_run(baseline.run_id)
            foreign_event = second_record["event_address"]
            foreign_dossier = second_record["dossier_address"]
            for address in (foreign_event, foreign_dossier):
                first_runtime.store.store.put_at(
                    address,
                    second_runtime.store.store.get(address),
                )
            first_record["event_history"] = [
                foreign_event,
                first_record["event_address"],
            ]
            first_record["dossier_history"] = [
                foreign_dossier,
                first_record["dossier_address"],
            ]
            path = first_runtime.store.runs / f"{baseline.run_id}.json"
            path.write_text(canonical_json(first_record), encoding="utf-8")

            with self.assertRaisesRegex(ValidationError, "authenticated modern suffix"):
                first_runtime.load_run_snapshot_at(
                    baseline.run_id,
                    event_address=foreign_event,
                    dossier_address=foreign_dossier,
                )
            self.assertFalse(foreign_assessment.verify(first_runtime))
            self.assertFalse(foreign_assessment.verify_without_rebuild(first_runtime))

    def test_historical_loading_rejects_an_injected_dossier_for_a_valid_event_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            draft = runtime.evaluate(fixture_manifest())
            initial = runtime.get_run(draft.run_id)
            pending = replace(
                draft,
                warnings=(*draft.warnings, "injected historical warning"),
                content_address="pending",
            )
            forged = replace(
                pending,
                content_address=runtime._dossier_address(pending),
            )
            runtime.store.store.put_at(forged.content_address, forged.to_dict())
            runtime.assign_review(
                draft.run_id,
                assignment_id="assessment-dossier-binding",
                reviewer="assessment-reviewer",
            )
            current = runtime.get_run(draft.run_id)
            current["dossier_history"][0] = forged.content_address
            path = runtime.store.runs / f"{draft.run_id}.json"
            path.write_text(canonical_json(current), encoding="utf-8")

            with self.assertRaisesRegex(ValidationError, "authenticated modern suffix"):
                runtime.load_run_snapshot_at(
                    draft.run_id,
                    event_address=initial["event_address"],
                    dossier_address=forged.content_address,
                )

    def test_current_loading_rejects_deletion_inside_authenticated_history(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            draft = runtime.evaluate(fixture_manifest())
            genesis_assessment = build_run_assessment(runtime, draft.run_id)
            runtime.assign_review(
                draft.run_id,
                assignment_id="assessment-history-deletion-one",
                reviewer="assessment-reviewer-one",
            )
            runtime.assign_review(
                draft.run_id,
                assignment_id="assessment-history-deletion-two",
                reviewer="assessment-reviewer-two",
            )
            path = runtime.store.runs / f"{draft.run_id}.json"
            truncated = json.loads(path.read_text(encoding="utf-8"))
            del truncated["event_history"][1]
            del truncated["dossier_history"][1]
            path.write_text(canonical_json(truncated), encoding="utf-8")

            with self.assertRaisesRegex(ValidationError, "authenticated modern suffix"):
                runtime.load_run_snapshot(draft.run_id)
            self.assertFalse(genesis_assessment.verify(runtime))
            self.assertFalse(genesis_assessment.verify_without_rebuild(runtime))

    def test_assessment_rejects_dossier_that_disagrees_with_terminal_review_event(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            draft = runtime.evaluate(fixture_manifest())
            predecessor = runtime.get_run(draft.run_id)
            accepted = runtime.review_run(
                draft.run_id,
                ReviewDecision(
                    review_id="assessment-semantic-accepted",
                    case_id=draft.case_id,
                    reviewer="assessment-reviewer",
                    state=ReviewState.ACCEPTED,
                    reviewed_hypothesis_ids=tuple(
                        item.hypothesis_id for item in draft.hypotheses
                    ),
                    rationale="Accepted after reviewing every retained research artifact.",
                    checked_claim_ids=tuple(item.evidence_id for item in draft.evidence),
                ),
            )
            assessment = build_run_assessment(runtime, accepted.run_id)

            rejected_log = runtime.load_event_log(predecessor["event_address"])
            runtime._append_snapshot_predecessor_binding(rejected_log, predecessor)
            rejected = ReviewDecision(
                review_id="assessment-semantic-rejected",
                case_id=draft.case_id,
                reviewer="assessment-reviewer",
                state=ReviewState.REJECTED,
                reviewed_hypothesis_ids=tuple(
                    item.hypothesis_id for item in draft.hypotheses
                ),
                rationale="Rejected after reviewing the same retained research artifacts.",
                checked_claim_ids=tuple(item.evidence_id for item in draft.evidence),
            )
            rejected_log.append(
                "review_recorded",
                rejected.to_dict(),
                event_id=rejected.review_id,
            )
            forged = runtime._readdress(replace(accepted, event_head=rejected_log.head))
            event_address = runtime.store.store.put(rejected_log.to_record())
            runtime.store.store.put_at(forged.content_address, forged.to_dict())
            current = runtime.get_run(draft.run_id)
            current["event_address"] = event_address
            current["event_history"][-1] = event_address
            current["dossier_address"] = forged.content_address
            current["dossier_history"][-1] = forged.content_address
            path = runtime.store.runs / f"{draft.run_id}.json"
            path.write_text(canonical_json(current), encoding="utf-8")

            with self.assertRaisesRegex(ValidationError, "latest review event"):
                runtime.load_run_snapshot(draft.run_id)
            self.assertFalse(assessment.verify(runtime))
            self.assertFalse(assessment.verify_without_rebuild(runtime))

    def test_assessment_rejects_assignment_after_terminal_review(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            draft = runtime.evaluate(fixture_manifest())
            accepted = runtime.review_run(
                draft.run_id,
                ReviewDecision(
                    review_id="assessment-terminal-review",
                    case_id=draft.case_id,
                    reviewer="assessment-reviewer",
                    state=ReviewState.ACCEPTED,
                    reviewed_hypothesis_ids=tuple(
                        item.hypothesis_id for item in draft.hypotheses
                    ),
                    rationale="Accepted after a complete terminal review.",
                    checked_claim_ids=tuple(item.evidence_id for item in draft.evidence),
                ),
            )
            current = runtime.get_run(accepted.run_id)
            forged_log = runtime.load_event_log(current["event_address"])
            runtime._append_snapshot_predecessor_binding(forged_log, current)
            assignment_body = {
                "assignment_id": "assessment-after-terminal-assignment",
                "run_id": accepted.run_id,
                "case_id": accepted.case_id,
                "reviewer": "second-reviewer",
                "queue_id": "terminal-review-queue",
                "due_at": "",
                "note": "This transition is impossible through assign_review.",
                "created_at": "2026-09-01T12:00:00+00:00",
            }
            forged_log.append(
                "review_assigned",
                assignment_body
                | {
                    "content_address": content_hash(
                        assignment_body,
                        prefix="review-assignment",
                    )
                },
                event_id=assignment_body["assignment_id"],
            )
            forged = runtime._readdress(replace(accepted, event_head=forged_log.head))
            event_address = runtime.store.store.put(forged_log.to_record())
            runtime.store.store.put_at(forged.content_address, forged.to_dict())
            current["event_address"] = event_address
            current["event_history"].append(event_address)
            current["dossier_address"] = forged.content_address
            current["dossier_history"].append(forged.content_address)
            path = runtime.store.runs / f"{draft.run_id}.json"
            path.write_text(canonical_json(current), encoding="utf-8")

            with self.assertRaisesRegex(ValidationError, "terminal review decision"):
                runtime.load_run_snapshot(draft.run_id)

    def test_assessment_builder_rejects_event_history_without_dossier_pair(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            draft = runtime.evaluate(fixture_manifest())
            runtime.assign_review(
                draft.run_id,
                assignment_id="assessment-unpaired-assignment",
                reviewer="assessment-reviewer",
            )
            path = runtime.store.runs / f"{draft.run_id}.json"
            unpaired = json.loads(path.read_text(encoding="utf-8"))
            unpaired["dossier_history"] = unpaired["dossier_history"][1:]
            path.write_text(canonical_json(unpaired), encoding="utf-8")

            with self.assertRaisesRegex(ValidationError, "event history cannot exceed"):
                build_run_assessment(runtime, draft.run_id)

    def test_verified_snapshot_constructor_enforces_persisted_history_limit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            dossier = runtime.evaluate(fixture_manifest())
            snapshot = runtime.load_run_snapshot(dossier.run_id)
            record = snapshot.run_record_dict()
            generated = [
                f"sha256:{index:064x}"
                for index in range(1, MAX_RUN_HISTORY_ENTRIES + 3)
                if f"sha256:{index:064x}"
                not in {record["event_address"], record["dossier_address"]}
            ][:MAX_RUN_HISTORY_ENTRIES]
            record["event_history"] = [*generated, record["event_address"]]
            record["dossier_history"] = [*generated, record["dossier_address"]]

            with self.assertRaisesRegex(ValidationError, "current-ended address list"):
                VerifiedRunSnapshot(
                    run_record=record,
                    manifest=snapshot.manifest,
                    event_record=snapshot.event_log.to_record(),
                    dossier=snapshot.dossier,
                    replay=snapshot.replay,
                )


if __name__ == "__main__":
    unittest.main()
