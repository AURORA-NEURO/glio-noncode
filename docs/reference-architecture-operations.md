# D04 operation catalog

This document is the detailed operation card for the 16 D04 reference operations. The aggregate layer owns case identity, context policy, source joins, expected outcomes, and receipt normalization. Family modules own their typed payload interpretation.

## Coordinate family

### `reference_registry`

Purpose: establish the public assembly reference used by downstream operations.

Inputs: assembly label, reference context, source receipt identifiers, and a bounded public assembly descriptor.

Output: supported reference state and a content-addressed result summary.

Controls: a foreign assembly context is out of domain; malformed assembly input is invalid; contradictory assembly identity is held as contradictory.

Evidence: NCBI Genome Reference Consortium assembly metadata, GRC documentation, and the checked-in public aggregate coordinate fixture.

### `liftover_chain`

Purpose: parse and summarize a public chain-format relationship between reference coordinate systems.

Inputs: source and target assembly labels, a bounded chain descriptor, and UCSC chain-format receipts.

Output: supported chain state, parsed chain summary, and informative parsing issue codes when applicable.

Controls: context mismatch is held before parsing; a malformed chain descriptor cannot be interpreted; conflicting source and target identities remain under review.

Evidence: UCSC chain format and LiftOver documentation plus the existing typed coordinate adapter.

### `liftover_ambiguity`

Purpose: classify whether a bounded coordinate mapping is unique, ambiguous, or unavailable.

Inputs: source interval, target interval candidates, mapping status, and public reference receipts.

Output: supported state with bounded ambiguity summary. A unique mapping may retain `ambiguity_unique` as an informative issue code.

Controls: foreign context, malformed candidate sets, and conflicting candidate identities are held at the architecture boundary.

Evidence: the coordinate fixture evaluator and public coordinate mapping documentation.

### `pangenome_coordinate`

Purpose: summarize a coordinate relationship against a public pangenome reference catalog.

Inputs: reference path label, pangenome path label, bounded mapping status, and HPRC receipts.

Output: supported state and bounded mapping summary.

Controls: context, malformed payload, and identity conflict are represented as review cases with one deterministic issue code each.

Evidence: Human Pangenome Reference Consortium public alignment catalog and data-use boundary.

## Annotation family

### `gencode_transcript_catalog`

Purpose: resolve a bounded transcript catalog entry against the selected reference context.

Inputs: catalog release, assembly, transcript role, source joins, and aggregate count fields.

Output: supported catalog state, catalog count, match count, and a content address.

Controls: the architecture does not dispatch foreign context, malformed catalog fields, or contradictory transcript identity.

Evidence: GENCODE human release and GTF format documentation.

### `mane_transcript_catalog`

Purpose: summarize a MANE transcript catalog match for the reference context.

Inputs: MANE release label, assembly, transcript accession class, and bounded match fields.

Output: supported catalog state and bounded catalog/match counts.

Controls: context, shape, and identity controls are held with explicit reason codes.

Evidence: NCBI and EMBL-EBI MANE public documentation and RefSeq resources.

### `regulatory_ontology_catalog`

Purpose: resolve a public regulatory or relation ontology label to a bounded catalog result.

Inputs: ontology identifier, release label, relation family, and aggregate match fields.

Output: supported catalog state and match counts.

Controls: a relation identifier from another reference context is not silently coerced; malformed or conflicting ontology fields are review cases.

Evidence: OBO Relation Ontology public catalog and the typed annotation fixture evaluator.

### `disease_ontology_mapping`

Purpose: summarize a public disease ontology mapping relevant to diffuse glioma reference analysis.

Inputs: Mondo term class, mapping direction, release label, and bounded match fields.

Output: supported mapping state and bounded counts.

Controls: no direct clinical subject data is part of this contract. Context mismatch, malformed term shape, and contradictory identifiers are held.

Evidence: OBO Mondo public catalog.

## Governance family

### `gene_alias_version_resolution`

Purpose: resolve a versioned gene nomenclature alias to a canonical public catalog result.

Inputs: alias catalog release, reference assembly, alias class, source receipts, and bounded counts.

Output: supported resolution state and primary/secondary counts.

Controls: context, malformed catalog shape, and alias identity conflict are held before the governance adapter.

Evidence: HGNC nomenclature and download boundaries.

### `population_frequency_adaptation`

Purpose: adapt a public population-frequency catalog summary to the reference context.

Inputs: catalog version, allele-frequency field class, assembly, and bounded count fields.

Output: supported adaptation state and primary/secondary counts.

Controls: no individual-level frequency rows are admitted. Foreign context, malformed frequency values, and contradictory catalog identity are held.

Evidence: gnomAD public data portal and governance adapter receipts.

### `reference_snapshot_manifest`

Purpose: close the source and version manifest for a reproducible reference snapshot.

Inputs: assembly version, catalog versions, source receipt IDs, and aggregate manifest fields.

Output: supported manifest state and bounded manifest counts.

Controls: missing or conflicting version joins remain under review instead of being repaired implicitly.

Evidence: NCBI, GENCODE, RefSeq, HGNC, and SPDX public reference receipts.

### `license_use_restriction`

Purpose: classify whether a public source receipt has an allowed use boundary for the aggregate release.

Inputs: SPDX identifier, source scope, license descriptor, and aggregate-use class.

Output: supported governance state and bounded restriction counts.

Controls: unknown or contradictory license identity is held; malformed license fields are invalid at the boundary.

Evidence: SPDX license list, public source terms, and governance policy checks.

## Release family

### `source_provenance_check`

Purpose: verify that a release candidate retains source receipts and content addresses.

Inputs: source IDs, public URIs, version labels, source scope, and address joins.

Output: accepted release provenance state and bounded output fields.

Controls: foreign context, malformed source records, and source identity conflicts are held.

Evidence: the source receipts in the aggregate fixture and the existing release-frontier adapter.

### `annotation_drift_detection`

Purpose: compare bounded annotation release summaries for deterministic drift signals.

Inputs: baseline and candidate release labels, catalog counts, context, and public evidence addresses.

Output: accepted drift result or a bounded review signal.

Controls: context mismatch is out of domain; malformed comparison fields are invalid; conflicting release identities are contradictory.

Evidence: GENCODE, MANE, ontology, and release-frontier fixtures.

### `reproducible_reference_bundle`

Purpose: produce a reproducible aggregate bundle manifest from the closed fixture and receipts.

Inputs: fixture address, evaluation address, review address, lineage address, and metrics address.

Output: accepted bundle state and output-field count.

Controls: the architecture holds cases with mismatched context, malformed payloads, or identity conflicts before bundle materialization.

Evidence: six D04 artifact specifications and the release-frontier bundle adapter.

### `reference_release_gate`

Purpose: apply the final public release contract to the composed reference runtime.

Inputs: evaluation closure, review closure, lineage closure, artifact inventory, and release checks.

Output: accepted release gate and a content-addressed release result.

Controls: any failed contract remains visible and blocks publication. A review case is acceptable only when it matches its declared control expectation and is included in the review queue.

Evidence: release-frontier checks, D04 quality gate, replay comparison, access policy, and invariant checks.

## Common receipt contract

All 16 operations expose the same aggregate receipt shape after family execution:

```text
case_id
operation_id
expected_state
observed_state
expected_result_state
observed_result_state
expected_issue_codes
observed_issue_codes
expected_counts
observed_counts
output_address
content_address
passed
```

The aggregate contract retains counts and addresses while excluding raw payload from receipts. This makes review, replay, and release checks stable across adapter families.
