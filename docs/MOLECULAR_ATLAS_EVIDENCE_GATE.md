# Molecular atlas evidence gate

This document defines the public aggregate evidence boundary for Domain 05
capabilities C05-C08:

- C05: IDH-mutant molecular-state atlas profile;
- C06: IDH-wildtype molecular-state atlas profile;
- C07: H3K27-altered molecular-state atlas profile;
- C08: replicate-aware histone-mark track harmonization.

The implementation is a research-use annotation boundary. It does not make a
patient-level assertion, expression call, activity call, causal claim, or
clinical decision.

## Public source boundary

The checked-in source receipts point to official public pages:

| Source | Purpose | URI |
| --- | --- | --- |
| ENCODE histone standards | ChIP-seq assay, replicate, and signal boundary | <https://www.encodeproject.org/chip-seq/histone/> |
| ENCODE histone pipeline | Released processing pipeline receipt | <https://www.encodeproject.org/pipelines/ENCPL272XAE/> |
| NCI adult CNS tumor reference | Adult glioma molecular vocabulary | <https://www.cancer.gov/types/brain/hp/adult-brain-treatment-pdq> |
| NCI childhood cancer data boundary | Pediatric molecular vocabulary boundary | <https://www.cancer.gov/research/areas/childhood/childhood-cancer-data-initiative> |
| NCI GDC lower-grade glioma study | Aggregate subtype and cohort vocabulary | <https://gdc.cancer.gov/about-data/publications/lgg_2015> |

The fixture does not download or vendor a source archive. It contains compact
aggregate rows shaped to these public contracts so state separation,
context-gating, replicate disagreement, and quarantine behavior remain
deterministic. The receipts identify source scope; they do not claim that the
synthetic rows occur verbatim in a source release.

## Fixture identity

The public descriptor is:

```json
{
  "fixture": "default_molecular_atlas_fixture"
}
```

The stable fixture version is `2026.08.d05-c05-c08.v1`. Its primary context key
is:

```text
GRCh38|diffuse_glioma|adult|stem_like|unknown|unknown
```

The evidence boundary is `public_aggregate_non_patient`. The fixture retains
five source receipts, sixteen records, four positive records, and twelve
controls. Every record has a declared operation, role, source ID, expected
state, and content address. No record payload contains subject, patient,
donor, or sample identifiers.

## C05-C07 state profile contract

The state adapter parses JSON, TSV, or CSV records into interval observations.
Each record retains molecular state, exact context key, assay, optional signal,
source version, and raw hash. Query execution applies these gates in order:

1. restrict records to the requested molecular state;
2. require interval overlap;
3. require exact context-key equality;
4. return a bounded state without selecting across state or context.

`supported` means one exact-state, exact-context record overlaps. `abstained`
means no requested-state record overlaps. `out_of_domain` means an overlapping
record exists but its exact context differs. `ambiguous` means more than one
compatible record overlaps and no record is selected.

The three state families are never collapsed:

| Capability | State family | Context emphasis |
| --- | --- | --- |
| C05 | IDH-mutant | adult diffuse glioma |
| C06 | IDH-wildtype | adult diffuse glioma |
| C07 | H3K27-altered | diffuse midline / territory-qualified |

The controls exercise age drift, no overlap, and duplicate compatible rows for
each state family. Absence is retained as abstention and is not a biological
negative.

## C08 histone contract

The histone adapter parses interval rows containing mark, signal, replicate,
caller, context, source, and version. BED coordinates are converted to the
one-based closed interval used by the workbench. Harmonization splits each
mark/context group at every observed boundary and computes median, minimum,
maximum, and spread for the active observations.

An interval is `supported` only when at least two replicate IDs are present and
the signal spread is within the declared tolerance. A single replicate is
`partial`. Signal disagreement beyond tolerance is `ambiguous`. Malformed
coordinates and required fields are quarantined as `invalid_histone_row` while
the receipt remains visible. Unobserved bases are not imputed.

The harmonizer emits a warning that signal is descriptive and not a calibrated
activity estimate. It does not infer enhancer activity, gene expression,
causality, or clinical consequence from a histone mark.

## Execution and quality floors

The accepted fixture executes:

| Artifact | Floor |
| --- | ---: |
| Evaluation receipts | 16 |
| Evaluation checks | 120 |
| Independent scenarios | 15 |
| Replay checks | 13 |
| Policy rules | 12 |
| Quality checks | 25 |
| Lineage nodes | 157 |
| Lineage edges | 158 |
| Accepted-only bundle entries | 4 |
| Runtime stages | 9 |
| Release checks | 12 |

Receipt summaries retain state, counts, issue codes, context, match or interval
IDs, replicate counts, signal spread, hashes, and bounded warnings. They omit
`input_text`, `payload`, `records`, and other executable collections.

## Policy rules

The policy module checks public aggregate scope, exact context, source closure,
absence of subject identifiers, state separation, positive support, visible
controls, no source fetch in parsing, absence-not-negative semantics,
ambiguity-not-selection semantics, histone replicate floors, and no activity or
causal inference fields.

Every failed policy remains visible. Publication requires accepted data,
execution, replay, scenarios, lineage, reconciliation, policy, and bundle
artifacts.

## Reproduction commands

```powershell
python -m glio_noncode audit-molecular-atlas-data examples/molecular-atlas-public-aggregate.json --output molecular-atlas-data.json
python -m glio_noncode evaluate-molecular-atlas-fixture examples/molecular-atlas-public-aggregate.json --output molecular-atlas-fixture.json
python -m glio_noncode replay-molecular-atlas-fixtures examples/molecular-atlas-public-aggregate.json --output molecular-atlas-replay.json
python -m glio_noncode molecular-atlas-quality-gate examples/molecular-atlas-public-aggregate.json --output molecular-atlas-quality.json
python -m glio_noncode molecular-atlas-metrics examples/molecular-atlas-public-aggregate.json --output molecular-atlas-metrics.json
python -m glio_noncode molecular-atlas-lineage examples/molecular-atlas-public-aggregate.json --output molecular-atlas-lineage.json
python -m glio_noncode molecular-atlas-reconciliation examples/molecular-atlas-public-aggregate.json --output molecular-atlas-reconciliation.json
python -m glio_noncode run-molecular-atlas-pipeline examples/molecular-atlas-pipeline-accepted.json --output molecular-atlas-pipeline.json
python -m glio_noncode build-molecular-atlas-release examples/molecular-atlas-public-aggregate.json --output molecular-atlas-release.json
```

The same command family runs in the repository workflow against the checked-in
descriptor.
