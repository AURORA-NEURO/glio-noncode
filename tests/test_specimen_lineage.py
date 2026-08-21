from __future__ import annotations

import unittest

from glio_noncode.specimen_lineage import (
    LineageAlphaState,
    LongitudinalSpecimenLinker,
    MultiRegionLineageResolver,
    PrimaryRecurrencePhaseMapper,
    SpecimenPhase,
    TreatmentExposureContextualizer,
)

CONTEXT = "GRCh38|glioma|adult|stem_like|unknown|unknown"


def specimen(specimen_id: str, subject_id: str, date: str, **extra: object) -> dict[str, object]:
    return {
        "specimen_id": specimen_id,
        "sample_id": specimen_id + "-sample",
        "subject_id": subject_id,
        "tissue": "tumor",
        "collection_time": date,
        **extra,
    }


class SpecimenLineageTests(unittest.TestCase):
    def test_multi_region_lineage_retains_edges_roots_and_leaves(self) -> None:
        result = MultiRegionLineageResolver().resolve(
            [
                {
                    "region_id": "r1",
                    "sample_id": "s1",
                    "subject_id": "u1",
                    "region_label": "primary",
                    "relationship": "root",
                },
                {
                    "region_id": "r2",
                    "sample_id": "s2",
                    "subject_id": "u1",
                    "region_label": "region-2",
                    "parent_region_id": "r1",
                    "relationship": "derived",
                },
                {
                    "region_id": "r3",
                    "sample_id": "s3",
                    "subject_id": "u1",
                    "region_label": "region-3",
                    "parent_region_id": "r1",
                    "relationship": "derived",
                },
            ],
            context_key=CONTEXT,
        )
        lineage = result.lineages[0]
        self.assertEqual(result.state, LineageAlphaState.SUPPORTED)
        self.assertEqual(lineage.roots, ("r1",))
        self.assertEqual(lineage.leaves, ("r2", "r3"))
        self.assertEqual(len(lineage.edges), 2)

    def test_multi_region_lineage_retains_missing_parent_and_cycle(self) -> None:
        missing = MultiRegionLineageResolver().resolve(
            [
                {
                    "region_id": "r1",
                    "sample_id": "s1",
                    "subject_id": "u1",
                    "region_label": "region",
                    "parent_region_id": "absent",
                    "relationship": "derived",
                }
            ]
        )
        self.assertEqual(missing.state, LineageAlphaState.PARTIAL)
        self.assertEqual(missing.lineages[0].missing_parent_ids, ("absent",))
        cyclic = MultiRegionLineageResolver().resolve(
            [
                {
                    "region_id": "r1",
                    "sample_id": "s1",
                    "subject_id": "u1",
                    "region_label": "one",
                    "parent_region_id": "r2",
                    "relationship": "derived",
                },
                {
                    "region_id": "r2",
                    "sample_id": "s2",
                    "subject_id": "u1",
                    "region_label": "two",
                    "parent_region_id": "r1",
                    "relationship": "derived",
                },
            ]
        )
        self.assertEqual(cyclic.state, LineageAlphaState.CONTRADICTORY)
        self.assertEqual(cyclic.lineages[0].cycle_region_ids, ("r1", "r2"))

    def test_longitudinal_linker_uses_declared_predecessor(self) -> None:
        result = LongitudinalSpecimenLinker().link(
            [
                specimen("s1", "u1", "2024-01-01"),
                specimen(
                    "s2",
                    "u1",
                    "2024-02-01",
                    predecessor_specimen_id="s1",
                ),
            ]
        )
        self.assertEqual(result.state, LineageAlphaState.SUPPORTED)
        self.assertEqual(result.links[0].ordering_basis, "declared_predecessor")
        self.assertEqual(result.links[0].gap_label, "31.0_days")

    def test_longitudinal_linker_orders_same_subject_and_flags_missing_time(self) -> None:
        result = LongitudinalSpecimenLinker().link(
            [
                specimen("s2", "u1", "2024-02-01"),
                specimen("s1", "u1", "2024-01-01"),
                specimen("s3", "u2", ""),
            ]
        )
        self.assertEqual(result.state, LineageAlphaState.PARTIAL)
        self.assertEqual(result.links[0].predecessor_specimen_id, "s1")
        self.assertIn("s3", result.unlinked_specimen_ids)

    def test_phase_mapper_requires_explicit_recurrence_evidence(self) -> None:
        result = PrimaryRecurrencePhaseMapper().map(
            [
                specimen("s1", "u1", "2024-01-01", phase="primary"),
                specimen("s2", "u1", "2024-02-01"),
                specimen("s3", "u1", "2024-03-01", phase="recurrence"),
            ]
        )
        self.assertEqual(result.state, LineageAlphaState.PARTIAL)
        phases = {item.specimen_id: item.phase for item in result.assignments}
        self.assertEqual(phases["s1"], SpecimenPhase.PRIMARY)
        self.assertEqual(phases["s2"], SpecimenPhase.UNKNOWN)
        self.assertEqual(phases["s3"], SpecimenPhase.RECURRENCE)

    def test_phase_mapper_retains_conflicting_labels(self) -> None:
        result = PrimaryRecurrencePhaseMapper().map(
            [specimen("s1", "u1", "2024-01-01", phase="primary|recurrence")]
        )
        self.assertEqual(result.state, LineageAlphaState.CONTRADICTORY)
        self.assertEqual(result.assignments[0].conflicting_labels, ("primary", "recurrence"))

    def test_treatment_contextualizer_returns_temporal_relations(self) -> None:
        result = TreatmentExposureContextualizer().contextualize(
            [
                specimen("pre", "u1", "2023-12-01"),
                specimen("on", "u1", "2024-02-01"),
                specimen("post", "u1", "2024-05-01"),
            ],
            [
                {
                    "exposure_id": "e1",
                    "subject_id": "u1",
                    "therapy_id": "drug-a",
                    "therapy_class": "alkylator",
                    "start_time": "2024-01-01",
                    "end_time": "2024-03-01",
                }
            ],
        )
        relations = {item.specimen_id: item.relation for item in result.contexts}
        self.assertEqual(
            relations, {"on": "on_treatment", "post": "post_treatment", "pre": "pre_treatment"}
        )
        self.assertEqual(result.state, LineageAlphaState.SUPPORTED)

    def test_treatment_contextualizer_retains_overlap_and_missing_time(self) -> None:
        result = TreatmentExposureContextualizer().contextualize(
            [specimen("s1", "u1", "2024-02-01"), specimen("s2", "u1", "")],
            [
                {
                    "exposure_id": "e1",
                    "subject_id": "u1",
                    "therapy_id": "drug-a",
                    "start_time": "2024-01-01",
                    "end_time": "2024-03-01",
                },
                {
                    "exposure_id": "e2",
                    "subject_id": "u1",
                    "therapy_id": "drug-b",
                    "start_time": "2024-02-01",
                    "end_time": "2024-04-01",
                },
            ],
        )
        self.assertEqual(result.state, LineageAlphaState.AMBIGUOUS)
        self.assertEqual(result.contexts[0].overlapping_exposure_ids, ("e2",))
        self.assertIn("s2", result.uncontextualized_specimen_ids)


if __name__ == "__main__":
    unittest.main()
