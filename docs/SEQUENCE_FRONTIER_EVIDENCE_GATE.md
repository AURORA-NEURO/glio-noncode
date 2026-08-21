# Sequence frontier evidence gate

## Purpose

This gate defines the bounded evidence boundary for Domain 06 C13-C16. It is
designed for deterministic local evaluation of sequence-regulatory adapters,
not for unreviewed biological or clinical conclusions. The checked-in fixture
is a public aggregate artifact with no subject-level records. External sources
are represented by versioned receipt summaries and content addresses.

The four operations are:

| Capability | Operation | Required positive state | Control states |
| --- | --- | --- | --- |
| C13 | `enhancer_grammar` | `accepted` | `review`, `review`, `out_of_domain` |
| C14 | `allele_saturation` | `accepted` | `review`, `review`, `out_of_domain` |
| C15 | `ensemble_disagreement` | `accepted` | `review`, `review`, `out_of_domain` |
| C16 | `sequence_evidence_publish` | `published` | `abstained`, `out_of_domain`, `invalid` |

The fixture contains 16 records total. Each operation receives one positive
record and three controls, so the same evaluator exercises successful,
uncertain, incomplete, and scope-invalid paths. The evaluator emits 120 checks:
seven per record plus eight fixture-wide checks. A passing evaluation requires
all checks to pass; review and abstention are valid data states inside the
fixture and are not silently promoted.

## Source boundary

The source matrix records five public references:

- NCBI RefSeq for reference sequence access and release context.
- GA4GH Variant Annotation standards for variant representation boundaries.
- ENCODE SCREEN for regulatory-region aggregate context.
- ENCODE transcription-factor experiment documentation for motif evidence
  provenance.
- Ensembl regulation documentation for regulatory annotation context.

The implementation retains source name, URL, release, retrieval date, summary,
and receipt hash. It does not fetch during fixture evaluation. A record is
accepted only when every referenced source ID resolves to a fixture receipt.

## State rules

`accepted` is reserved for a positive record whose operation-specific
requirements pass. `published` additionally requires valid publication
metadata and a complete sequence-evidence bundle. `review` indicates that the
record is structurally usable but fails a declared evidence floor. `abstained`
indicates missing evidence without a negative biological claim. `out_of_domain`
means the context or boundary is incompatible. `invalid` means required
metadata or record structure is malformed.

The evaluator keeps issue codes specific:

- grammar: `grammar_no_motif_hits`, `grammar_coverage_below_floor`,
  `sequence_context_mismatch`;
- saturation: `saturation_uncertainty_above_floor`,
  `saturation_no_positive_effect`;
- ensemble: `ensemble_disagreement_above_floor`,
  `ensemble_insufficient_predictions`;
- publication: `empty_sequence_records`, `publish_metadata_invalid`.

## Gate sequence

The runtime composes these stages:

1. fixture and source-closure audit;
2. contract and schema resolution;
3. adapter execution for all 16 records;
4. evaluation check generation;
5. policy and review-budget evaluation;
6. quality checks and bundle construction;
7. lineage and reconciliation;
8. trace and metrics creation;
9. release manifest and sanitized export generation.

The quality gate requires 11 checks, including fixture identity, source
closure, evaluation acceptance, policy acceptance, schema validity, replay
stability, lineage closure, reconciliation, bundle integrity, trace completeness,
and export sanitization. A release is blocked if any quality check fails or if
the runtime is configured to fail on review outcomes.

## Non-claims

The gate does not establish motif binding, chromatin occupancy, expression,
causality, treatment response, clinical significance, or calibrated model
probability. It records the declared adapter output and its uncertainty,
provenance, scope, and review state. Any broader use requires a separately
reviewed evidence boundary and new fixtures.
