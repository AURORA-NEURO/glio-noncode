from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from glio_noncode.reference_annotation_bundle import ReferenceAnnotationBundleBuilder
from glio_noncode.reference_annotation_fixture_eval import evaluate_reference_annotation_fixture
from glio_noncode.reference_annotation_quality_gate import (
    evaluate_reference_annotation_quality_gate,
)
from glio_noncode.reference_annotation_release import (
    ReferenceAnnotationReleaseState,
    build_reference_annotation_release_manifest,
    verify_reference_annotation_release_manifest,
    write_reference_annotation_release_manifest,
)
from glio_noncode.reference_annotation_replay import replay_reference_annotation_evaluation


class ReferenceAnnotationReleaseTests(unittest.TestCase):
    def _manifest(self):
        evaluation = evaluate_reference_annotation_fixture()
        quality = evaluate_reference_annotation_quality_gate()
        bundle = ReferenceAnnotationBundleBuilder().build(evaluation, accepted_only=True)
        replay = replay_reference_annotation_evaluation(evaluation)
        return build_reference_annotation_release_manifest(evaluation, quality, bundle, replay)

    def test_release_manifest_is_published_and_verified(self) -> None:
        manifest = self._manifest()
        self.assertEqual(manifest.state, ReferenceAnnotationReleaseState.PUBLISHED)
        self.assertTrue(manifest.publishable)
        self.assertEqual(verify_reference_annotation_release_manifest(manifest), ())
        self.assertEqual(manifest.accepted_count, 4)
        self.assertEqual(manifest.review_count, 0)

    def test_release_manifest_has_four_capabilities_and_five_sources(self) -> None:
        manifest = self._manifest()
        self.assertEqual(len(manifest.capability_ids), 4)
        self.assertEqual(len(manifest.source_ids), 5)
        self.assertEqual(manifest.entry_count, 4)

    def test_release_manifest_write_is_json_and_addressed(self) -> None:
        manifest = self._manifest()
        with tempfile.TemporaryDirectory() as directory:
            path = write_reference_annotation_release_manifest(
                manifest, Path(directory) / "release.json"
            )
            text = path.read_text(encoding="utf-8")
            self.assertTrue(text.endswith("\n"))
            self.assertIn(manifest.content_address, text)

    def test_review_bundle_cannot_be_published(self) -> None:
        evaluation = evaluate_reference_annotation_fixture()
        quality = evaluate_reference_annotation_quality_gate()
        bundle = ReferenceAnnotationBundleBuilder().build(evaluation, accepted_only=False)
        replay = replay_reference_annotation_evaluation(evaluation)
        manifest = build_reference_annotation_release_manifest(evaluation, quality, bundle, replay)
        self.assertEqual(manifest.state, ReferenceAnnotationReleaseState.REVIEW)
        self.assertFalse(manifest.publishable)

    def test_tampered_manifest_is_detected(self) -> None:
        manifest = self._manifest()
        tampered = manifest.__class__(
            manifest.release_id,
            manifest.fixture_id,
            manifest.fixture_version,
            manifest.context_key,
            manifest.state,
            manifest.source_ids,
            manifest.capability_ids,
            manifest.entry_count,
            3,
            manifest.review_count,
            manifest.checks,
            manifest.content_address,
        )
        self.assertIn(
            "count-reconciliation", verify_reference_annotation_release_manifest(tampered)
        )
