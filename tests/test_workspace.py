import unittest

from glio_noncode.cohort_discovery import (
    CohortDiscoveryEvidenceBuilder,
    CohortQuery,
    CohortQueryBuilder,
    CohortVariantRecord,
)
from glio_noncode.models import ReferenceContext, VariantIdentity, VariantKind, VariantOrigin
from glio_noncode.regulatory_tracks import RegulatoryTrackParser
from glio_noncode.workspace import (
    CaseWorkspaceBuilder,
    CohortWorkspaceBuilder,
    RegulatoryTrackBrowser,
    VariantExplorer,
    WorkspaceKind,
    WorkspaceQuery,
    WorkspaceRecordType,
    WorkspaceState,
)


class WorkspaceTests(unittest.TestCase):
    CONTEXT = ReferenceContext("GRCh38", "glioma", "adult", "stem_like", territory="core")

    def _variant(self, variant_id: str, position: int = 100) -> VariantIdentity:
        return VariantIdentity(
            variant_id=variant_id,
            kind=VariantKind.SNV,
            chromosome="7",
            start=position,
            end=position,
            reference="A",
            alternate="T",
            genome_build="GRCh38",
            origin=VariantOrigin.SOMATIC,
            sample_id="tumor-1",
        )

    def test_case_workspace_exposes_exact_context_sections_and_filters(self) -> None:
        from glio_noncode.models import CaseManifest

        manifest = CaseManifest(
            case_id="case-1",
            subject_id="subject-1",
            context=self.CONTEXT,
            variants=(self._variant("v1"), self._variant("v2", 200)),
            input_versions={"source-1": "sha256:input"},
        )
        workspace = CaseWorkspaceBuilder().build(manifest)
        self.assertEqual(workspace.kind, WorkspaceKind.CASE)
        self.assertEqual(workspace.state, WorkspaceState.PARTIAL)
        self.assertEqual(
            {section.section_id for section in workspace.sections},
            {"variants", "regulatory-elements", "hypotheses", "evidence", "validation"},
        )
        page = workspace.search(
            WorkspaceQuery(
                context_key=self.CONTEXT.key,
                record_types=(WorkspaceRecordType.VARIANT,),
                chromosome="7",
                start=150,
                end=250,
            )
        )
        self.assertEqual(page.state, WorkspaceState.SUPPORTED)
        self.assertEqual([record.record_id for record in page.records], ["v2"])
        self.assertEqual(page.facets["record_type"], {"variant": 1})

    def test_cohort_workspace_keeps_background_and_controls_as_separate_records(self) -> None:
        records = (
            CohortVariantRecord(
                record_id="r1",
                variant=self._variant("v1"),
                context_key=self.CONTEXT.key,
                source_id="cohort-1",
                sample_id="tumor-1",
                sequence_context="ACGT",
            ),
        )
        result = CohortQueryBuilder().build(
            CohortQuery("q1", self.CONTEXT.key),
            records,
        )
        evidence = CohortDiscoveryEvidenceBuilder().build("e1", result)
        workspace = CohortWorkspaceBuilder().build(evidence)
        self.assertEqual(workspace.kind, WorkspaceKind.COHORT)
        self.assertEqual(
            workspace.search(
                WorkspaceQuery(record_types=(WorkspaceRecordType.COHORT_RECORD,))
            ).total_matches,
            1,
        )
        self.assertEqual(
            workspace.search(WorkspaceQuery(record_types=(WorkspaceRecordType.SUMMARY,))).state,
            WorkspaceState.ABSENT,
        )
        self.assertEqual(workspace.warnings[0].split()[0], "Cohort")

    def test_variant_explorer_groups_declared_variant_relationships(self) -> None:
        from glio_noncode.models import CaseManifest

        manifest = CaseManifest(
            case_id="case-2",
            subject_id="subject-2",
            context=self.CONTEXT,
            variants=(self._variant("v1"),),
        )
        workspace = CaseWorkspaceBuilder().build(manifest)
        detail = VariantExplorer().inspect(workspace, "v1")
        self.assertEqual(detail.state, WorkspaceState.SUPPORTED)
        self.assertIsNotNone(detail.variant)
        self.assertEqual(detail.related_record_ids, ())
        missing = VariantExplorer().inspect(workspace, "missing")
        self.assertEqual(missing.state, WorkspaceState.ABSTAINED)

    def test_regulatory_browser_supports_interval_overlap_and_context_abstention(self) -> None:
        batch = RegulatoryTrackParser().parse_text(
            "7\t99\t120\treg-1\t800\t+\n",
            source_id="track-1",
            genome_build="GRCh38",
        )
        workspace = RegulatoryTrackBrowser().build(batch, context_key=self.CONTEXT.key)
        page = workspace.search(
            WorkspaceQuery(record_types=(WorkspaceRecordType.REGULATORY_ELEMENT,))
        )
        self.assertEqual(page.state, WorkspaceState.SUPPORTED)
        overlap = (
            RegulatoryTrackBrowser()
            .build(batch, context_key=self.CONTEXT.key)
            .search(WorkspaceQuery(chromosome="7", start=110, end=111))
        )
        self.assertEqual(overlap.total_matches, 1)
        ood = workspace.search(
            WorkspaceQuery(context_key="GRCh38|glioma|pediatric|stem_like|core|unknown")
        )
        self.assertEqual(ood.state, WorkspaceState.OUT_OF_DOMAIN)

    def test_search_pagination_facets_and_command_palette_are_deterministic(self) -> None:
        from glio_noncode.models import CaseManifest

        manifest = CaseManifest(
            case_id="case-3",
            subject_id="subject-3",
            context=self.CONTEXT,
            variants=(self._variant("v2", 200), self._variant("v1", 100)),
        )
        workspace = CaseWorkspaceBuilder().build(manifest)
        first = workspace.search(
            WorkspaceQuery(record_types=(WorkspaceRecordType.VARIANT,), limit=1)
        )
        second = workspace.search(
            WorkspaceQuery(record_types=(WorkspaceRecordType.VARIANT,), offset=1, limit=1)
        )
        self.assertEqual(first.total_matches, 2)
        self.assertEqual(first.records[0].record_id, "v1")
        self.assertEqual(second.records[0].record_id, "v2")
        palette = workspace.search(WorkspaceQuery(text="GRCh38:7:100"))
        self.assertEqual(palette.total_matches, 1)
        self.assertEqual(
            palette.content_address,
            workspace.search(WorkspaceQuery(text="GRCh38:7:100")).content_address,
        )


if __name__ == "__main__":
    unittest.main()
