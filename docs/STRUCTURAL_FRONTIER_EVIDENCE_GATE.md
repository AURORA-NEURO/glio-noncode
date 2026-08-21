# Domain 02 C13-C16 evidence gate

This document defines the release boundary for the fourth Domain 02 structural
frontier family. The family covers four operations:

| Capability | Operation | Core adapter | Published state |
| --- | --- | --- | --- |
| GNC-D02-C13 | Tandem-repeat interpretation | `TandemRepeatInterpreter` | accepted or review |
| GNC-D02-C14 | Compound noncoding haplotype evaluation | `CompoundHaplotypeEvaluator` | accepted or review |
| GNC-D02-C15 | Breakpoint uncertainty propagation | `BreakpointUncertaintyPropagator` | accepted or review |
| GNC-D02-C16 | Structural-variant evidence export | `StructuralVariantEvidenceExporter` | published or blocked |

The release surface is intentionally larger than the four adapter calls. A
record is only useful when its source receipt, exact context, expected state,
observed state, deterministic address, review issues, and downstream lineage
are all inspectable. The checked-in aggregate fixture therefore exercises the
adapters through data audit, fixture evaluation, replay, scenario, quality,
bundle, lineage, and runtime boundaries.

## Evidence boundary

The fixture is aggregate and public-data-shaped. It is not a patient case and
does not contain subject identifiers, clinical measurements, raw sequences, or
sample-level payloads. Every record uses the exact context key:

```text
GRCh38|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment
```

The context has six ordered dimensions:

1. reference assembly;
2. disease family;
3. age stratum;
4. molecular or morphological stratum;
5. material or territory stratum;
6. treatment-exposure stratum.

The order is part of the contract. A record with the same labels in a
different order is a different context and fails the audit. The evaluator does
not repair context drift, infer missing strata, or merge near matches.

Source receipts describe public aggregate resource surfaces used to shape the
fixture. They are not claims that the fixture reproduces a source release.
The source boundary points to [NCBI dbVar](https://www.ncbi.nlm.nih.gov/dbvar/),
the [dbVar FTP manifest](https://www.ncbi.nlm.nih.gov/dbvar/content/ftp_manifest/),
the [dbVar Study Browser](https://www.ncbi.nlm.nih.gov/dbvar/studies/), the
[dbVar Human Structural Variation Data Hub](https://www.ncbi.nlm.nih.gov/dbvar/content/human_hub/),
and the [gnomAD-SV v4 release description](https://gnomad.broadinstitute.org/news/2023-11-v4-structural-variants/).

## Catalog requirements

`StructuralFrontierFixtureCatalog` enforces the following requirements before
any adapter executes:

| Requirement | Release floor | Failure behavior |
| --- | ---: | --- |
| operation coverage | 4 distinct operations | audit rejected |
| positive records | 4 | audit rejected |
| review controls | 8 | audit rejected |
| source receipts | 4 in the checked-in fixture | audit rejected |
| context dimensions | exactly 6 | audit rejected |
| aggregate scope | true for fixture and receipts | audit rejected |
| record identity | unique and content-addressed | audit rejected |
| source membership | each record references a declared source | audit rejected |
| sensitive payload keys | none | audit rejected |

The audit sorts source and record identifiers before hashing. Sorting removes
input-order noise while retaining duplicate detection. It does not hide
duplicate identifiers: duplicates are reported as explicit issue codes.

## Positive records

The four positive records each exercise one operation and one expected result:

### C13 tandem repeat

The positive repeat observation supplies a motif, reference and alternate copy
number, an uncertainty value, a repeat unit, and an interval. The adapter
validates the motif and interval, compares the copy delta to uncertainty, and
classifies the result as expansion, contraction, or within uncertainty. The
fixture expects one expansion with no review issue.

The controls cover an invalid motif and a delta that remains within the stated
uncertainty. Invalid input is review-visible; a non-expansion is not promoted
to an expansion merely because its delta is non-zero.

### C14 compound haplotype

The positive haplotype declares required alleles and observes every required
allele in a complete phase-compatible record. The evaluator preserves the
required set, observed set, phase state, missing alleles, and compatibility
decision. The fixture expects a compatible result.

The controls cover incomplete observation and unknown phase. An incomplete
haplotype is review with `incomplete_haplotype`; an unknown phase may retain a
complete result but remains a review fixture control. The distinction keeps a
complete observation separate from a fully resolved phase claim.

### C15 breakpoint uncertainty

The positive breakpoint record supplies left and right intervals, confidence,
and a breakpoint identifier. The adapter preserves interval widths and emits a
bounded uncertainty receipt. The fixture expects a high-confidence result.

The controls cover inverted intervals and low confidence. Inversion is a
validation issue, while low confidence is a review state. The adapter never
collapses interval uncertainty into a point estimate.

### C16 structural evidence export

The positive export record contains the required evidence identity, evidence
type, source ID, and exact context. The exporter sorts evidence deterministically,
deduplicates source identifiers, and publishes a content-addressed bundle.

The controls omit one required field and introduce context drift. Both are
blocked from publication with `validation_error`. A bundle is not published
because its rows happen to be parseable; required fields and context must pass.

## Evaluation receipts

`evaluate_structural_frontier_fixture` produces one operation receipt for each
positive or control record. Each receipt contains:

- record ID and operation;
- expected and observed fixture states;
- expected and observed result states;
- stable issue codes;
- a sanitized output address;
- operation-specific counts;
- explicit check results;
- a short review-safe detail string.

The canonical fixture has twelve receipts and seventy-two checks. Checks are
not inferred from a final boolean. They assert expected state, result state,
issue codes, operation counts, and a content address. A record can therefore
fail for a precise reason without exposing its input payload.

Failure receipts are also addressed. Validation failures include the record ID
in the sanitized output before hashing, so two invalid controls cannot collide
at the replay layer simply because both returned zero counts.

## Replay contract

Replay reloads the fixture from disk and reruns all operations. The expectation
requires the fixture identity, exact context, declared source set, minimum
check count, four positive records, and eight controls. Replay rejects:

- duplicate fixture identities;
- duplicate record IDs;
- duplicate output addresses;
- missing source IDs;
- context mismatch;
- a changed evaluation content address;
- an evaluation that does not pass its own checks.

The replay report contains case receipts and a report address. It is suitable
for a CI artifact because it contains only identifiers, counts, states, issue
codes, and hashes.

## Scenario matrix

The scenario matrix executes every record independently rather than trusting
the aggregate evaluator. Each scenario declares the expected fixture state,
expected result state, and required issue codes. The matrix currently contains
twelve scenarios: four positives and eight controls. Its independent execution
guards against an aggregate loop that accidentally masks one record's result.

Scenario classes are deliberately small:

| Scenario class | Expected result |
| --- | --- |
| positive operation | accepted or published |
| malformed operation | review or invalid |
| uncertainty boundary | accepted without over-classification |
| incomplete phase | review |
| publication boundary | invalid and not published |

## Quality gate

The quality gate reconciles twenty checks:

1. data audit;
2. fixture evaluation;
3. check floor;
4. replay;
5. scenario matrix;
6. positive floor;
7. control floor;
8. operation coverage;
9. contract floor;
10. context agreement;
11. source agreement;
12. deterministic evaluation;
13. fixture identity;
14. aggregate scope;
15. addressed receipts;
16. contract-state coverage;
17. sanitized boundary;
18. receipt identity;
19. lineage audit;
20. lineage shape.

Context agreement checks the catalog, every record, evaluation, audit, and
lineage graph. Source agreement checks the catalog, audit, and lineage source
sets. These checks intentionally fail on a single drifted record even when the
top-level catalog context remains unchanged.

The canonical fixture must finish in `accepted` quality-gate state. Review
controls inside the fixture are expected and do not make the aggregate gate
fail; they are evidence that review semantics are executable. A fixture-level
failure, a malformed catalog, an address collision, or a publication-state
violation does fail the gate.

## Lineage graph

The lineage graph has four node kinds:

```text
source -> fixture -> record -> result
```

The canonical graph contains 29 nodes and 36 edges:

- four source nodes;
- one fixture node;
- twelve record nodes;
- twelve result nodes;
- four source-to-fixture declarations;
- one fixture containment edge;
- twelve fixture-to-record edges;
- twelve record-to-result edges;
- seven result-to-source declarations represented by source references.

All node and edge addresses are deterministic. The graph exposes operation,
state, context, source references, and result addresses, but not raw evidence
payloads. Lineage audit checks endpoint existence, relation shape, address
format, context agreement, source coverage, and result pairing.

## Runtime pipeline

`run_structural_frontier_pipeline` accepts a bounded batch request and executes
the four stages in order:

```text
tandem_repeat
    -> compound_haplotype
    -> breakpoint_uncertainty
    -> structural_evidence_export
```

Each stage receipt reports input and output counts, state, issue codes, and a
stage address. The final manifest is published only when the export stage
reaches `published` and all earlier stages remain acceptable. Count
conservation checks make sure an adapter cannot silently create or discard
records between stages.

The accepted pipeline example has one observation, one haplotype evaluation,
one breakpoint interval, and two exported evidence rows. The review example
shows the same boundary with invalid motif, incomplete haplotype, and export
validation issues. Both examples are deterministic and aggregate-only.

## Local commands

Run the complete C13-C16 surface from the repository root:

```powershell
python -m glio_noncode audit-structural-frontier-data `
  examples/structural-frontier-public-aggregate.json `
  --output structural-frontier-data.json
python -m glio_noncode evaluate-structural-frontier-fixture `
  examples/structural-frontier-public-aggregate.json `
  --output structural-frontier-fixture.json
python -m glio_noncode replay-structural-frontier-fixtures `
  examples/structural-frontier-public-aggregate.json `
  --required-context-key "GRCh38|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment" `
  --output structural-frontier-replay.json
python -m glio_noncode structural-frontier-quality-gate `
  examples/structural-frontier-public-aggregate.json `
  --output structural-frontier-quality.json
python -m glio_noncode evaluate-structural-frontier-scenarios `
  examples/structural-frontier-public-aggregate.json `
  --output structural-frontier-scenarios.json
python -m glio_noncode structural-frontier-contracts `
  --output structural-frontier-contracts.json
python -m glio_noncode structural-frontier-lineage `
  examples/structural-frontier-public-aggregate.json `
  --output structural-frontier-lineage.json
python -m glio_noncode run-structural-frontier-pipeline `
  examples/structural-frontier-pipeline-accepted.json `
  --output structural-frontier-pipeline.json
```

The bundle command requires the quality gate and can project JSON, CSV, or
Markdown. Review-state fixtures can be written only with `--allow-review`,
which makes the release decision explicit at the command boundary.

## Extension rules

Future structural frontier work should follow this sequence:

1. add or extend a typed adapter with explicit accepted and review states;
2. add a public aggregate receipt and at least one negative control;
3. add fixture checks that assert counts, issue codes, and addresses;
4. add independent replay and scenario coverage;
5. add or update the quality gate, lineage graph, bundle, and runtime;
6. expose the operation through the package API and CLI;
7. add the command to CI and update the capability ledger;
8. run the full test suite before publishing.

An adapter is not counted as verified when only its happy path is present.
Verification requires a deterministic, aggregate-safe evidence boundary with
review controls and release-surface coverage.
