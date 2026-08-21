"""Bundle rendering and verification tests for Domain 02 C13-C16."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.errors import ValidationError
from glio_noncode.structural_frontier_bundle import (
    StructuralFrontierBundleFormat,
    StructuralFrontierEvidenceBundleBuilder,
)
from glio_noncode.structural_frontier_public_data import StructuralFrontierFixtureState

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "structural-frontier-public-aggregate.json"


class StructuralFrontierBundleTests(unittest.TestCase):
    def test_canonical_bundle_has_twelve_entries_and_component_summaries(self) -> None:
        bundle = StructuralFrontierEvidenceBundleBuilder().build(FIXTURE, bundle_id="canonical-frontier")
        self.assertTrue(bundle.accepted)
        self.assertEqual(bundle.state, StructuralFrontierFixtureState.ACCEPTED)
        self.assertEqual(len(bundle.entries), 12)
        self.assertEqual(sum(entry.entry_class == "positive" for entry in bundle.entries), 4)
        self.assertEqual(sum(entry.entry_class == "review" for entry in bundle.entries), 8)
        self.assertEqual(bundle.component_summaries["fixture"]["check_count"], 72)
        self.assertEqual(bundle.component_summaries["quality"]["check_count"], 20)
        self.assertEqual(bundle.component_summaries["lineage"]["node_count"], 29)
        self.assertEqual(bundle.component_summaries["lineage"]["edge_count"], 36)

    def test_entries_are_sorted_and_capability_mapped(self) -> None:
        bundle = StructuralFrontierEvidenceBundleBuilder().build(FIXTURE, bundle_id="ordered-frontier")
        keys = [(entry.entry_class, entry.capability_id, entry.entry_id) for entry in bundle.entries]
        self.assertEqual(keys, sorted(keys))
        self.assertEqual({entry.capability_id for entry in bundle.entries}, {
            "GNC-D02-C13", "GNC-D02-C14", "GNC-D02-C15", "GNC-D02-C16"
        })
        self.assertTrue(all(entry.evidence_address.startswith("sha256:") for entry in bundle.entries))

    def test_json_render_and_verification_round_trip(self) -> None:
        bundle = StructuralFrontierEvidenceBundleBuilder().build(FIXTURE, bundle_id="json-frontier")
        payload = json.loads(bundle.render(StructuralFrontierBundleFormat.JSON))
        self.assertTrue(StructuralFrontierEvidenceBundleBuilder.verify(payload))
        self.assertEqual(payload["entry_count"], 12)
        self.assertEqual(payload["positive_entry_count"], 4)
        self.assertEqual(payload["review_entry_count"], 8)

    def test_csv_render_has_header_and_twelve_rows(self) -> None:
        bundle = StructuralFrontierEvidenceBundleBuilder().build(FIXTURE, bundle_id="csv-frontier")
        lines = bundle.render(StructuralFrontierBundleFormat.CSV).splitlines()
        self.assertEqual(len(lines), 13)
        self.assertIn("capability_id", lines[0])
        self.assertTrue(all(line.startswith(("positive:", "review:")) for line in lines[1:]))

    def test_markdown_render_has_boundary_and_sources(self) -> None:
        bundle = StructuralFrontierEvidenceBundleBuilder().build(FIXTURE, bundle_id="markdown-frontier")
        text = bundle.render(StructuralFrontierBundleFormat.MARKDOWN)
        self.assertTrue(text.startswith("# Structural frontier evidence bundle"))
        self.assertIn("GNC-D02-C16", text)
        self.assertIn("## Boundary", text)
        self.assertIn("ncbi-dbvar-ftp-manifest", text)

    def test_write_infers_format_from_extension(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            csv_path = root / "bundle.csv"
            markdown_path = root / "bundle.md"
            builder = StructuralFrontierEvidenceBundleBuilder()
            builder.write(FIXTURE, csv_path)
            builder.write(FIXTURE, markdown_path)
            self.assertTrue(csv_path.read_text(encoding="utf-8").startswith("entry_id,"))
            self.assertTrue(markdown_path.read_text(encoding="utf-8").startswith("# Structural frontier evidence bundle"))

    def test_write_accepts_explicit_format(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "bundle.out"
            StructuralFrontierEvidenceBundleBuilder().write(
                FIXTURE,
                output,
                output_format=StructuralFrontierBundleFormat.MARKDOWN,
            )
            self.assertTrue(output.read_text(encoding="utf-8").startswith("# Structural frontier evidence bundle"))

    def test_verifier_ignores_convenience_counts(self) -> None:
        bundle = StructuralFrontierEvidenceBundleBuilder().build(FIXTURE, bundle_id="convenience-frontier")
        payload = copy.deepcopy(bundle.to_dict())
        payload["entry_count"] = 99
        payload["positive_entry_count"] = 0
        self.assertTrue(StructuralFrontierEvidenceBundleBuilder.verify(payload))

    def test_verifier_rejects_tampered_structural_body(self) -> None:
        bundle = StructuralFrontierEvidenceBundleBuilder().build(FIXTURE, bundle_id="tamper-frontier")
        payload = copy.deepcopy(bundle.to_dict())
        payload["entries"][0]["summary"] = "changed"
        self.assertFalse(StructuralFrontierEvidenceBundleBuilder.verify(payload))

    def test_failed_quality_gate_requires_explicit_review_flag(self) -> None:
        raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
        raw["positives"][0]["expected_counts"]["expanded"] = 99
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "failed.json"
            path.write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaisesRegex(ValidationError, "requires a passing quality gate"):
                StructuralFrontierEvidenceBundleBuilder().build(path)
            review = StructuralFrontierEvidenceBundleBuilder().build(path, allow_review=True)
        self.assertEqual(review.state, StructuralFrontierFixtureState.REVIEW)
        self.assertFalse(review.accepted)

    def test_bundle_is_deterministic_for_same_identity(self) -> None:
        first = StructuralFrontierEvidenceBundleBuilder().build(FIXTURE, bundle_id="stable-frontier")
        second = StructuralFrontierEvidenceBundleBuilder().build(FIXTURE, bundle_id="stable-frontier")
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(first.to_dict(), second.to_dict())

    def test_bundle_excludes_raw_and_sensitive_markers(self) -> None:
        bundle = StructuralFrontierEvidenceBundleBuilder().build(FIXTURE, bundle_id="sanitized-frontier")
        serialized = json.dumps(bundle.to_dict(), sort_keys=True)
        self.assertNotIn("raw_record", serialized)
        self.assertNotIn("patient_id", serialized)
        self.assertNotIn("subject_id", serialized)


if __name__ == "__main__":
    unittest.main()
