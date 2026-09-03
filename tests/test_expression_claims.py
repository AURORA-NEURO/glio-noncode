from __future__ import annotations

import json
import unittest
from dataclasses import FrozenInstanceError, replace

from glio_noncode.errors import ValidationError
from glio_noncode.evidence import EvidenceGraph
from glio_noncode.expression_claims import (
    DEFAULT_RNA_CLAIM_POLICY,
    DETERMINISTIC_CREATED_AT,
    MAX_RNA_CLAIM_BATCH_ITEMS,
    PRODUCED_BY,
    RNA_CONSEQUENCE_CHANNEL,
    RNAClaimBatch,
    RNAClaimPolicy,
    RNAElementGeneTarget,
    element_gene_edge_id,
    expression_claims_capabilities,
    expression_claims_schema,
    match_rna_consequences,
    matches_rna_consequence,
    public_projection,
    rna_consequence_to_claim,
    validate_rna_consequence,
)
from glio_noncode.expression_evidence import (
    AllelicDirection,
    ExpressionDirection,
    RegulatoryDirection,
    RNAConsequenceEvidence,
    RNAEvidenceState,
)
from glio_noncode.hypotheses import HypothesisBuilder
from glio_noncode.models import (
    EdgeType,
    EvidenceClaim,
    EvidenceState,
    EvidenceTier,
    HypothesisEdge,
    ReferenceContext,
    SupportLevel,
)
from glio_noncode.serialization import content_hash


def reference_context(**overrides: object) -> ReferenceContext:
    values: dict[str, object] = {
        "genome_build": "GRCh38",
        "disease_class": "diffuse_glioma",
        "age_group": "adult",
        "cell_state": "malignant",
        "territory": "enhancing_core",
        "treatment_phase": "pre_treatment",
        "assay_support": ("rna_seq",),
        "source_version": "context-2026-09",
    }
    values.update(overrides)
    return ReferenceContext(**values)  # type: ignore[arg-type]


def target(
    *,
    variant_id: str = "variant:chr3-181711925-A-G",
    element_id: str = "element:SOX2-enhancer-1",
    gene_id: str = "gene:SOX2",
    context: ReferenceContext | None = None,
) -> RNAElementGeneTarget:
    return RNAElementGeneTarget(
        variant_id=variant_id,
        element_id=element_id,
        gene_id=gene_id,
        context=context or reference_context(),
    )


def consequence(
    state: RNAEvidenceState = RNAEvidenceState.SUPPORTED,
    *,
    prediction_id: str = "prediction:sox2:01",
    variant_id: str = "variant:chr3-181711925-A-G",
    feature_id: str = "gene:SOX2",
    context_key: str | None = None,
    expression_robust_z: float | None = None,
    allelic_log2_ratio: float | None = None,
    allelic_q_value: float | None = None,
) -> RNAConsequenceEvidence:
    expression_state = None
    expression_direction = None
    expression_address = None
    if state is RNAEvidenceState.SUPPORTED:
        expression_state = RNAEvidenceState.SUPPORTED
        expression_direction = ExpressionDirection.UP
        expression_robust_z = 4.2 if expression_robust_z is None else expression_robust_z
        expression_address = content_hash(
            {"prediction_id": prediction_id, "component": "expression"},
            prefix="expression-outlier",
        )
    elif state is RNAEvidenceState.CONTRADICTORY:
        expression_state = RNAEvidenceState.SUPPORTED
        expression_direction = ExpressionDirection.DOWN
        expression_robust_z = -4.2 if expression_robust_z is None else expression_robust_z
        expression_address = content_hash(
            {"prediction_id": prediction_id, "component": "expression-opposite"},
            prefix="expression-outlier",
        )
    elif state is RNAEvidenceState.MEASURED_NEGATIVE:
        expression_state = RNAEvidenceState.MEASURED_NEGATIVE
        expression_direction = ExpressionDirection.NEUTRAL
        expression_robust_z = 0.2 if expression_robust_z is None else expression_robust_z
        expression_address = content_hash(
            {"prediction_id": prediction_id, "component": "expression-negative"},
            prefix="expression-outlier",
        )
    elif state is RNAEvidenceState.OUT_OF_DOMAIN:
        expression_state = RNAEvidenceState.OUT_OF_DOMAIN
        expression_direction = ExpressionDirection.UNKNOWN
        expression_address = content_hash(
            {"prediction_id": prediction_id, "component": "expression-foreign"},
            prefix="expression-outlier",
        )

    allelic_state = None
    allelic_direction = None
    allelic_address = None
    if allelic_log2_ratio is not None or allelic_q_value is not None:
        allelic_state = state
        allelic_direction = (
            AllelicDirection.ALT_ENRICHED
            if state is RNAEvidenceState.SUPPORTED
            else AllelicDirection.REF_ENRICHED
        )
        allelic_address = content_hash(
            {"prediction_id": prediction_id, "component": "allelic"},
            prefix="allelic-imbalance",
        )

    return RNAConsequenceEvidence(
        prediction_id=prediction_id,
        prediction_address=content_hash(
            {"prediction_id": prediction_id}, prefix="regulatory-effect-prediction"
        ),
        variant_id=variant_id,
        feature_id=feature_id,
        context_key=context_key or reference_context().key,
        predicted_direction=RegulatoryDirection.GAIN,
        state=state,
        expression_state=expression_state,
        expression_direction=expression_direction,
        expression_robust_z=expression_robust_z,
        expression_result_address=expression_address,
        allelic_state=allelic_state,
        allelic_direction=allelic_direction,
        allelic_log2_ratio=allelic_log2_ratio,
        allelic_q_value=allelic_q_value,
        allelic_result_address=allelic_address,
        reason_codes=(f"bridge_fixture_{state.value}",),
    )


class TargetAndStateMappingTests(unittest.TestCase):
    def test_edge_address_is_exactly_the_native_builder_address(self) -> None:
        destination = target()
        expected = HypothesisBuilder._edge_id(  # noqa: SLF001 - contract parity test
            destination.element_id,
            destination.gene_id,
            EdgeType.ELEMENT_TO_GENE,
        )
        self.assertEqual(destination.edge_id, expected)
        self.assertEqual(
            element_gene_edge_id(destination.element_id, destination.gene_id), expected
        )

    def test_target_round_trip_and_tamper_detection(self) -> None:
        destination = target()
        self.assertEqual(RNAElementGeneTarget.from_json(destination.to_json()), destination)
        raw = destination.to_dict()
        raw["edge_id"] = "edge-00000000000000000000"
        with self.assertRaisesRegex(ValidationError, "edge_id"):
            RNAElementGeneTarget.from_mapping(raw)
        raw = destination.to_dict() | {"unexpected": True}
        with self.assertRaisesRegex(ValidationError, "unknown fields"):
            RNAElementGeneTarget.from_mapping(raw)

    def test_exact_match_uses_variant_gene_and_full_context_key(self) -> None:
        evidence = consequence()
        self.assertTrue(matches_rna_consequence(evidence, target()))
        mismatches = (
            target(variant_id="variant:other"),
            target(gene_id="gene:OLIG2"),
            target(context=reference_context(cell_state="stem_like")),
        )
        for destination in mismatches:
            with self.subTest(destination=destination):
                self.assertFalse(matches_rna_consequence(evidence, destination))
                with self.assertRaisesRegex(ValidationError, "does not match target"):
                    rna_consequence_to_claim(evidence, destination)

    def test_every_rna_state_maps_one_to_one(self) -> None:
        expected = {
            RNAEvidenceState.SUPPORTED: EvidenceState.SUPPORTED,
            RNAEvidenceState.CONTRADICTORY: EvidenceState.CONTRADICTORY,
            RNAEvidenceState.MEASURED_NEGATIVE: EvidenceState.MEASURED_NEGATIVE,
            RNAEvidenceState.OUT_OF_DOMAIN: EvidenceState.OUT_OF_DOMAIN,
            RNAEvidenceState.ABSTAINED: EvidenceState.ABSTAINED,
        }
        observed: dict[RNAEvidenceState, EvidenceState] = {}
        for state, native_state in expected.items():
            with self.subTest(state=state):
                claim = rna_consequence_to_claim(consequence(state), target())
                observed[state] = claim.state
                self.assertEqual(claim.state, native_state)
                if state in (RNAEvidenceState.OUT_OF_DOMAIN, RNAEvidenceState.ABSTAINED):
                    self.assertIsNone(claim.score)
                    self.assertEqual(claim.confidence, 0.0)
                elif state is RNAEvidenceState.MEASURED_NEGATIVE:
                    self.assertEqual(claim.score, DEFAULT_RNA_CLAIM_POLICY.measured_negative_score)
                else:
                    self.assertGreater(claim.score or 0.0, 0.0)
        self.assertEqual(observed, expected)
        self.assertNotIn(EvidenceState.ABSENT, observed.values())
        self.assertNotIn(EvidenceState.UNSUPPORTED, observed.values())

    def test_inconsistent_or_unsafe_consequence_is_rejected(self) -> None:
        invalid = RNAConsequenceEvidence(
            prediction_id="prediction:invalid",
            prediction_address="regulatory-effect-prediction:invalid",
            variant_id=target().variant_id,
            feature_id=target().gene_id,
            context_key=target().context.key,
            predicted_direction=RegulatoryDirection.GAIN,
            state=RNAEvidenceState.SUPPORTED,
            expression_state=None,
            expression_direction=None,
            expression_robust_z=None,
            expression_result_address=None,
            allelic_state=None,
            allelic_direction=None,
            allelic_log2_ratio=None,
            allelic_q_value=None,
            allelic_result_address=None,
            reason_codes=("directional_support",),
        )
        with self.assertRaisesRegex(ValidationError, "no measured RNA component"):
            rna_consequence_to_claim(invalid, target())

        unsafe = RNAConsequenceEvidence(
            prediction_id="prediction:invalid-code",
            prediction_address="regulatory-effect-prediction:invalid-code",
            variant_id=target().variant_id,
            feature_id=target().gene_id,
            context_key=target().context.key,
            predicted_direction=RegulatoryDirection.GAIN,
            state=RNAEvidenceState.ABSTAINED,
            expression_state=None,
            expression_direction=None,
            expression_robust_z=None,
            expression_result_address=None,
            allelic_state=None,
            allelic_direction=None,
            allelic_log2_ratio=None,
            allelic_q_value=None,
            allelic_result_address=None,
            reason_codes=("free text is not a stable code",),
        )
        with self.assertRaisesRegex(ValidationError, "reason_codes"):
            rna_consequence_to_claim(unsafe, target())


class ClaimDerivationTests(unittest.TestCase):
    def test_claim_is_native_immutable_and_content_deterministic(self) -> None:
        evidence = consequence()
        first = rna_consequence_to_claim(evidence, target())
        second = rna_consequence_to_claim(evidence, target())
        self.assertIsInstance(first, EvidenceClaim)
        self.assertEqual(first, second)
        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual(first.created_at, DETERMINISTIC_CREATED_AT)
        self.assertEqual(first.produced_by, PRODUCED_BY)
        self.assertEqual(first.tier, EvidenceTier.COMPUTED)
        self.assertEqual(first.channel, RNA_CONSEQUENCE_CHANNEL)
        self.assertEqual(first.depends_on, tuple(sorted(first.depends_on)))
        with self.assertRaises(FrozenInstanceError):
            first.score = 0.99  # type: ignore[misc]

    def test_retained_owner_is_explicit_deterministic_and_round_trips(self) -> None:
        evidence = consequence()
        destination = target()
        owner = content_hash({"kind": "retained-rna-consequence-batch"})
        standalone = rna_consequence_to_claim(evidence, destination)
        owned = rna_consequence_to_claim(
            evidence,
            destination,
            retained_owner_address=owner,
        )

        self.assertNotIn("retained_owner_address", standalone.payload)
        self.assertEqual(standalone.depends_on, tuple(standalone.payload["source_addresses"]))
        self.assertEqual(owned.depends_on, (owner,))
        self.assertEqual(owned.payload["retained_owner_address"], owner)
        self.assertEqual(owned.payload["source_addresses"], standalone.payload["source_addresses"])
        self.assertNotEqual(owned.evidence_id, standalone.evidence_id)
        self.assertEqual(public_projection(owned), owned.to_dict())

        batch = match_rna_consequences(
            (evidence,),
            (destination,),
            retained_owner_address=owner,
        )
        self.assertEqual(batch.claims, (owned,))
        self.assertEqual(RNAClaimBatch.from_json(batch.to_json()), batch)

        tampered = owned.to_dict()
        tampered["payload"]["retained_owner_address"] = content_hash(
            {"kind": "different-retained-batch"}
        )
        with self.assertRaisesRegex(ValidationError, "evidence_id"):
            public_projection(EvidenceClaim.from_dict(tampered))

    def test_retained_owner_requires_an_exact_canonical_sha256_address(self) -> None:
        class StringSubclass(str):
            pass

        invalid = (
            "sha256:" + "A" * 64,
            "sha256:" + "a" * 63,
            "rna-consequence-evidence:" + "a" * 64,
            StringSubclass("sha256:" + "a" * 64),
            1,
        )
        for owner in invalid:
            with self.subTest(owner=owner):
                with self.assertRaisesRegex(ValidationError, "canonical sha256"):
                    rna_consequence_to_claim(
                        consequence(),
                        target(),
                        retained_owner_address=owner,  # type: ignore[arg-type]
                    )

    def test_public_consequence_validator_closes_leaf_address_namespaces(self) -> None:
        evidence = consequence(allelic_log2_ratio=1.2, allelic_q_value=0.01)
        self.assertIs(validate_rna_consequence(evidence), evidence)
        malformed = {
            "prediction_address": "sha256:" + "a" * 64,
            "expression_result_address": "expression-outlier:" + "A" * 64,
            "allelic_result_address": "allelic-imbalance:" + "a" * 63,
        }
        for field_name, address in malformed.items():
            with self.subTest(field_name=field_name):
                with self.assertRaisesRegex(ValidationError, field_name):
                    validate_rna_consequence(replace(evidence, **{field_name: address}))
        with self.assertRaisesRegex(ValidationError, "exact RNAConsequenceEvidence"):
            validate_rna_consequence(object())

    def test_score_is_bounded_transparent_and_does_not_sum_components(self) -> None:
        evidence = consequence(
            expression_robust_z=3.5,
            allelic_log2_ratio=1.0,
            allelic_q_value=0.05,
        )
        claim = rna_consequence_to_claim(evidence, target())
        derivation = claim.payload["derivation"]
        self.assertEqual(derivation["expression_strength"], 0.5)
        self.assertEqual(derivation["allelic_strength"], 0.5)
        self.assertEqual(claim.score, 0.4)
        self.assertEqual(claim.confidence, DEFAULT_RNA_CLAIM_POLICY.multi_component_confidence)
        self.assertIn("not summed", derivation["rationale"])
        self.assertLessEqual(claim.score or 0.0, 0.8)

    def test_changed_consequence_changes_claim_id_and_content(self) -> None:
        first = rna_consequence_to_claim(consequence(expression_robust_z=3.6), target())
        second = rna_consequence_to_claim(consequence(expression_robust_z=5.5), target())
        self.assertNotEqual(first.evidence_id, second.evidence_id)
        self.assertNotEqual(first.payload, second.payload)

    def test_policy_is_validated_and_changes_are_explicit(self) -> None:
        policy = RNAClaimPolicy(max_directional_score=0.5)
        claim = rna_consequence_to_claim(
            consequence(expression_robust_z=3.5), target(), policy=policy
        )
        self.assertEqual(claim.score, 0.25)
        self.assertEqual(claim.payload["policy"]["max_directional_score"], 0.5)
        with self.assertRaisesRegex(ValidationError, "positive"):
            RNAClaimPolicy(expression_saturation_z=0.0)
        with self.assertRaisesRegex(ValidationError, "must not be below"):
            RNAClaimPolicy(single_component_confidence=0.8, multi_component_confidence=0.7)

    def test_public_payload_is_sample_free_and_contains_only_summaries(self) -> None:
        claim = rna_consequence_to_claim(
            consequence(allelic_log2_ratio=1.1, allelic_q_value=0.004), target()
        )
        projection = public_projection(claim)
        rendered = json.dumps(projection, sort_keys=True)
        self.assertNotIn("sample_key", rendered)
        self.assertNotIn("sample_id", rendered)
        self.assertNotIn("subject_id", rendered)
        self.assertNotIn("patient_id", rendered)
        self.assertNotIn("cohort_values", rendered)
        self.assertNotIn("observations", rendered)
        self.assertNotIn("target_value", rendered)
        self.assertTrue(projection["payload"]["privacy"]["raw_measurements_excluded"])

    def test_native_graph_keeps_all_rna_claims_in_one_dependence_group(self) -> None:
        destination = target()
        graph = EvidenceGraph()
        supported = rna_consequence_to_claim(
            consequence(prediction_id="prediction:supported"), destination
        )
        negative = rna_consequence_to_claim(
            consequence(
                RNAEvidenceState.MEASURED_NEGATIVE,
                prediction_id="prediction:negative",
            ),
            destination,
        )
        graph.extend((supported, negative))
        edge = HypothesisEdge(
            edge_id=destination.edge_id,
            edge_type=EdgeType.ELEMENT_TO_GENE,
            source_id=destination.element_id,
            target_id=destination.gene_id,
            support=0.0,
            uncertainty=1.0,
            context_fit=1.0,
            claim_ids=(supported.evidence_id, negative.evidence_id),
            support_level=SupportLevel.UNKNOWN,
        )
        aggregate = graph.aggregate(edge)
        self.assertEqual(aggregate.channel_groups, ("expression",))
        self.assertEqual(aggregate.supported_claim_ids, (supported.evidence_id,))
        self.assertEqual(aggregate.negative_claim_ids, (negative.evidence_id,))


class BatchMatchingTests(unittest.TestCase):
    def fixture(
        self,
    ) -> tuple[tuple[RNAConsequenceEvidence, ...], tuple[RNAElementGeneTarget, ...]]:
        matched = consequence(prediction_id="prediction:matched")
        unmatched = consequence(
            prediction_id="prediction:unmatched",
            variant_id="variant:unmatched",
            feature_id="gene:UNMATCHED",
        )
        ambiguous = consequence(
            prediction_id="prediction:ambiguous",
            variant_id="variant:ambiguous",
            feature_id="gene:AMBIGUOUS",
        )
        destinations = (
            target(),
            target(
                variant_id="variant:ambiguous",
                element_id="element:ambiguous:a",
                gene_id="gene:AMBIGUOUS",
            ),
            target(
                variant_id="variant:ambiguous",
                element_id="element:ambiguous:b",
                gene_id="gene:AMBIGUOUS",
            ),
            target(
                variant_id="variant:orphan",
                element_id="element:orphan",
                gene_id="gene:ORPHAN",
            ),
        )
        return (matched, unmatched, ambiguous), destinations

    def test_batch_reports_unmatched_and_ambiguous_without_guessing(self) -> None:
        evidence, destinations = self.fixture()
        batch = match_rna_consequences(evidence, destinations)
        self.assertEqual(len(batch.claims), 1)
        self.assertEqual(batch.matched_evidence_addresses, (evidence[0].content_address,))
        self.assertEqual(batch.unmatched_evidence_addresses, (evidence[1].content_address,))
        self.assertEqual(batch.ambiguous_evidence_addresses, (evidence[2].content_address,))
        self.assertEqual(len(batch.unmatched_target_addresses), 3)
        self.assertFalse(batch.complete)
        self.assertEqual(batch.claims[0].edge_id, destinations[0].edge_id)

    def test_batch_is_input_order_independent_and_round_trips(self) -> None:
        evidence, destinations = self.fixture()
        forward = match_rna_consequences(evidence, destinations)
        reverse = match_rna_consequences(iter(reversed(evidence)), iter(reversed(destinations)))
        self.assertEqual(forward, reverse)
        self.assertEqual(forward.to_json(), reverse.to_json())
        self.assertEqual(RNAClaimBatch.from_json(forward.to_json()), forward)

    def test_one_shot_iterables_preserve_single_item_compatibility(self) -> None:
        evidence = consequence()
        destination = target()
        expected = match_rna_consequences((evidence,), (destination,))
        observed = match_rna_consequences(iter((evidence,)), iter((destination,)))
        self.assertEqual(observed, expected)
        self.assertEqual(observed.to_json(), expected.to_json())

    def test_complete_matching_and_strict_mode(self) -> None:
        evidence = (consequence(),)
        destinations = (target(),)
        batch = match_rna_consequences(evidence, destinations, require_complete=True)
        self.assertTrue(batch.complete)
        self.assertFalse(batch.unmatched_target_addresses)
        broken_evidence, broken_targets = self.fixture()
        with self.assertRaisesRegex(ValidationError, "matching is incomplete"):
            match_rna_consequences(broken_evidence, broken_targets, require_complete=True)

    def test_duplicate_evidence_and_targets_fail_closed(self) -> None:
        evidence = consequence()
        destination = target()
        duplicate_evidence = RNAConsequenceEvidence.from_mapping(evidence.to_dict())
        duplicate_destination = RNAElementGeneTarget.from_mapping(destination.to_dict())
        targets_started = False

        def untouched_targets():
            nonlocal targets_started
            targets_started = True
            yield destination

        with self.assertRaisesRegex(ValidationError, "duplicate RNA consequences"):
            match_rna_consequences((evidence, duplicate_evidence), untouched_targets())
        self.assertFalse(targets_started)
        with self.assertRaisesRegex(ValidationError, "duplicate destinations"):
            match_rna_consequences((evidence,), (destination, duplicate_destination))

    def test_distinct_evidence_identities_may_share_one_match_key(self) -> None:
        evidence = (
            consequence(prediction_id="prediction:same-key:a"),
            consequence(prediction_id="prediction:same-key:b"),
        )
        batch = match_rna_consequences(evidence, (target(),), require_complete=True)
        self.assertEqual(len(batch.claims), 2)
        self.assertEqual(
            batch.matched_evidence_addresses,
            tuple(sorted(item.content_address for item in evidence)),
        )
        self.assertEqual(len({claim.evidence_id for claim in batch.claims}), 2)

    def test_exact_advertised_target_limit_is_accepted(self) -> None:
        context = reference_context()
        destinations = (
            target(element_id=f"element:limit:{index}", context=context)
            for index in range(MAX_RNA_CLAIM_BATCH_ITEMS)
        )
        batch = match_rna_consequences((), destinations)
        self.assertEqual(len(batch.target_addresses), MAX_RNA_CLAIM_BATCH_ITEMS)
        self.assertEqual(len(batch.unmatched_target_addresses), MAX_RNA_CLAIM_BATCH_ITEMS)

    def test_unbounded_iterables_stop_at_the_advertised_limit(self) -> None:
        evidence_reads = 0
        target_started = False

        def endless_evidence():
            nonlocal evidence_reads
            item = consequence()
            while True:
                evidence_reads += 1
                yield item

        def untouched_targets():
            nonlocal target_started
            target_started = True
            yield target()

        with self.assertRaisesRegex(
            ValidationError,
            rf"evidence exceeds the maximum of {MAX_RNA_CLAIM_BATCH_ITEMS} items",
        ):
            match_rna_consequences(endless_evidence(), untouched_targets())
        self.assertEqual(evidence_reads, MAX_RNA_CLAIM_BATCH_ITEMS + 1)
        self.assertFalse(target_started)

        target_reads = 0

        def endless_targets():
            nonlocal target_reads
            item = target()
            while True:
                target_reads += 1
                yield item

        with self.assertRaisesRegex(
            ValidationError,
            rf"targets exceeds the maximum of {MAX_RNA_CLAIM_BATCH_ITEMS} items",
        ):
            match_rna_consequences((consequence(),), endless_targets())
        self.assertEqual(target_reads, MAX_RNA_CLAIM_BATCH_ITEMS + 1)

    def test_batch_round_trip_detects_claim_and_receipt_tampering(self) -> None:
        batch = match_rna_consequences((consequence(),), (target(),))
        raw = json.loads(batch.to_json())
        raw["claims"][0]["confidence"] = 0.99
        with self.assertRaisesRegex(ValidationError, "evidence_id"):
            RNAClaimBatch.from_mapping(raw)

        raw = json.loads(batch.to_json())
        raw["matched_count"] = 99
        with self.assertRaisesRegex(ValidationError, "matched_count"):
            RNAClaimBatch.from_mapping(raw)

        raw = json.loads(batch.to_json())
        raw["content_address"] = "rna-claim-batch:" + "0" * 64
        with self.assertRaisesRegex(ValidationError, "content_address"):
            RNAClaimBatch.from_mapping(raw)

    def test_empty_batch_is_valid_deterministic_and_complete(self) -> None:
        batch = match_rna_consequences((), ())
        self.assertTrue(batch.complete)
        self.assertEqual(batch.claims, ())
        self.assertEqual(RNAClaimBatch.from_json(batch.to_json()), batch)


class SurfaceContractTests(unittest.TestCase):
    def test_capabilities_are_deterministic_and_complete(self) -> None:
        first = expression_claims_capabilities()
        self.assertEqual(first, expression_claims_capabilities())
        self.assertEqual(
            set(first["native_state_mapping"]),
            {state.value for state in RNAEvidenceState},
        )
        self.assertEqual(first["channel"], RNA_CONSEQUENCE_CHANNEL)
        self.assertTrue(first["privacy"]["sample_free_payloads"])
        self.assertIn("exact_three_key_matching", first["operations"])
        self.assertIn("bounded_batch_matching", first["operations"])
        self.assertIn("retained_owner_dependency_binding", first["operations"])
        self.assertEqual(
            set(first["dependency_modes"]),
            {"standalone", "retained_owner"},
        )
        self.assertEqual(
            first["limits"],
            {
                "max_evidence_items": MAX_RNA_CLAIM_BATCH_ITEMS,
                "max_target_items": MAX_RNA_CLAIM_BATCH_ITEMS,
            },
        )

    def test_schema_is_deterministic_and_declares_strict_surfaces(self) -> None:
        contract = expression_claims_schema()
        self.assertEqual(contract, expression_claims_schema())
        self.assertEqual(contract["schema_version"], "1.0.0")
        for definition in contract["$defs"].values():
            self.assertFalse(definition["additionalProperties"])
            self.assertTrue(set(definition["required"]) <= set(definition["properties"]))
        rendered = json.dumps(contract, sort_keys=True)
        self.assertNotIn("sample_key", rendered)
        self.assertNotIn("patient_id", rendered)
        owner_schema = contract["$defs"]["EvidenceClaim"]["properties"]["payload"]["properties"][
            "retained_owner_address"
        ]
        self.assertEqual(owner_schema["pattern"], "^sha256:[0-9a-f]{64}$")
        batch_properties = contract["$defs"]["RNAClaimBatch"]["properties"]
        for field_name in (
            "evidence_addresses",
            "target_addresses",
            "matched_evidence_addresses",
            "unmatched_evidence_addresses",
            "ambiguous_evidence_addresses",
            "unmatched_target_addresses",
            "claims",
        ):
            self.assertEqual(batch_properties[field_name]["maxItems"], MAX_RNA_CLAIM_BATCH_ITEMS)
            if field_name != "claims":
                self.assertTrue(batch_properties[field_name]["uniqueItems"])

    def test_public_projection_rejects_foreign_native_claims(self) -> None:
        foreign = EvidenceClaim(
            evidence_id="foreign",
            edge_id="edge-foreign",
            source_id="foreign",
            channel="qtl",
            state=EvidenceState.SUPPORTED,
            tier=EvidenceTier.COMPUTED,
            score=0.5,
            confidence=0.5,
            context=reference_context(),
            summary="foreign claim",
        )
        with self.assertRaisesRegex(ValidationError, "matched RNA"):
            public_projection(foreign)
        with self.assertRaisesRegex(ValidationError, "public object"):
            public_projection(object())


if __name__ == "__main__":
    unittest.main()
