from __future__ import annotations

import unittest

from glio_noncode.validation_beta import (
    AlleleSpecificReporterPlanner,
    BaseEditingDesignPlanner,
    CRISPRaDesignPlanner,
    CRISPRiDesignPlanner,
    GuideDesignConstraints,
    PerturbationMode,
    PrimeEditingDesignPlanner,
    ValidationBetaState,
    ValidationBetaTarget,
)

CONTEXT = "GRCh38|glioma|adult|stem_like|core|unknown"
OTHER_CONTEXT = "GRCh38|glioma|adult|differentiated|core|unknown"


def target(
    target_id: str = "target-1",
    *,
    context_key: str = CONTEXT,
    sequence: str | None = None,
    variant_offset: int = 20,
    reference: str = "C",
    alternate: str = "T",
) -> ValidationBetaTarget:
    sequence = sequence or ("A" * variant_offset + reference + "A" * 20)
    return ValidationBetaTarget(
        target_id=target_id,
        variant_id=f"variant-{target_id}",
        element_id=f"element-{target_id}",
        sequence=sequence,
        variant_offset=variant_offset,
        reference_allele=reference,
        alternate_allele=alternate,
        context_key=context_key,
        source_id="sequence-source",
        source_version="v1",
        raw_hash=f"raw-{target_id}",
    )


def constraints(
    mode: PerturbationMode, *, max_guides: int = 20, **kwargs: object
) -> GuideDesignConstraints:
    return GuideDesignConstraints(
        design_id=f"{mode.value}-design",
        context_key=CONTEXT,
        mode=mode,
        max_guides=max_guides,
        **kwargs,
    )


class ValidationBetaTests(unittest.TestCase):
    def test_crispri_and_crispra_generate_context_gated_candidates(self) -> None:
        crispri = CRISPRiDesignPlanner().plan((target(),), constraints(PerturbationMode.CRISPRI))
        crispra = CRISPRaDesignPlanner().plan((target(),), constraints(PerturbationMode.CRISPRA))
        self.assertEqual(crispri.state, ValidationBetaState.READY_FOR_REVIEW)
        self.assertEqual(crispra.state, ValidationBetaState.READY_FOR_REVIEW)
        self.assertTrue(crispri.guides)
        self.assertEqual(crispri.guides[0].mode, PerturbationMode.CRISPRI)
        self.assertTrue(all(item.variant_overlap for item in crispri.guides))
        self.assertTrue(all("not predicted" in " ".join(item.notes) for item in crispri.guides))
        self.assertTrue(crispri.content_address.startswith("sha256:"))

    def test_crispri_blocks_context_mismatch_and_optional_pam_gate(self) -> None:
        mismatch = CRISPRiDesignPlanner().plan(
            (target(context_key=OTHER_CONTEXT),), constraints(PerturbationMode.CRISPRI)
        )
        self.assertEqual(mismatch.state, ValidationBetaState.BLOCKED)
        self.assertIn("target-1:context_mismatch", mismatch.blockers)
        pam_blocked = CRISPRiDesignPlanner().plan(
            (target(),), constraints(PerturbationMode.CRISPRI, require_pam=True, max_guides=20)
        )
        self.assertEqual(pam_blocked.state, ValidationBetaState.BLOCKED)
        self.assertIn("target-1:no_candidate_meets_declared_constraints", pam_blocked.blockers)

    def test_base_editing_requires_supported_substitution_and_edit_window(self) -> None:
        package = BaseEditingDesignPlanner().plan(
            (target(),),
            constraints(
                PerturbationMode.BASE_EDITING,
                editing_window_start=4,
                editing_window_end=8,
            ),
        )
        self.assertEqual(package.state, ValidationBetaState.READY_FOR_REVIEW)
        self.assertTrue(package.guides)
        self.assertTrue(all(item.edit_payload == "C>T" for item in package.guides))
        self.assertTrue(all(4 <= 20 - item.start_offset <= 8 for item in package.guides))
        unsupported = BaseEditingDesignPlanner().plan(
            (target(reference="A", alternate="C", sequence="A" * 20 + "A" + "A" * 20),),
            constraints(PerturbationMode.BASE_EDITING),
        )
        self.assertEqual(unsupported.state, ValidationBetaState.BLOCKED)
        self.assertIn("target-1:unsupported_base_edit_substitution", unsupported.blockers)

    def test_prime_editing_retains_pbs_rtt_and_flank_blocker(self) -> None:
        package = PrimeEditingDesignPlanner().plan(
            (target(),),
            constraints(
                PerturbationMode.PRIME_EDITING,
                pbs_length=13,
                rtt_length=10,
                max_guides=20,
            ),
        )
        self.assertEqual(package.state, ValidationBetaState.READY_FOR_REVIEW)
        self.assertTrue(package.guides)
        self.assertTrue(all(item.pbs_sequence == "A" * 13 for item in package.guides))
        self.assertTrue(
            all(item.rtt_sequence and item.rtt_sequence.startswith("T") for item in package.guides)
        )
        short_flank = PrimeEditingDesignPlanner().plan(
            (target(variant_offset=5, sequence="A" * 5 + "C" + "A" * 20),),
            constraints(PerturbationMode.PRIME_EDITING, max_guides=20),
        )
        self.assertEqual(short_flank.state, ValidationBetaState.BLOCKED)
        self.assertIn("target-1:prime_editing_flank_shortage", short_flank.blockers)

    def test_allele_specific_reporter_keeps_reference_alternate_pair_and_budget(self) -> None:
        package = AlleleSpecificReporterPlanner().plan(
            (target(),),
            constraints(PerturbationMode.ALLELE_SPECIFIC_REPORTER, max_guides=2),
        )
        self.assertEqual(package.state, ValidationBetaState.READY_FOR_REVIEW)
        self.assertEqual({item.allele for item in package.constructs}, {"reference", "alternate"})
        alternate = next(item for item in package.constructs if item.allele == "alternate")
        self.assertEqual(alternate.sequence[20], "T")
        over_budget = AlleleSpecificReporterPlanner().plan(
            (target("one"), target("two")),
            constraints(PerturbationMode.ALLELE_SPECIFIC_REPORTER, max_guides=2),
        )
        self.assertEqual(over_budget.state, ValidationBetaState.BLOCKED)
        self.assertIn("max_constructs_exceeded", over_budget.blockers)

    def test_mapping_constructor_preserves_version_and_alternate_sequence(self) -> None:
        item = ValidationBetaTarget.from_mapping(
            {
                "target_id": "mapped",
                "variant_id": "v-mapped",
                "element_id": "enh-mapped",
                "sequence": "A" * 10 + "C" + "A" * 10,
                "variant_offset": 10,
                "reference_allele": "C",
                "alternate_allele": "G",
                "context_key": CONTEXT,
                "source_version": "snapshot-2",
            }
        )
        self.assertEqual(item.source_version, "snapshot-2")
        self.assertEqual(item.alternate_sequence[10], "G")
        self.assertTrue(item.to_dict()["raw_hash"].startswith("sha256:"))


if __name__ == "__main__":
    unittest.main()
