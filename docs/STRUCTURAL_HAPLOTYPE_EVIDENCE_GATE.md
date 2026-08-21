# Structural haplotype evidence gate

This document defines the public aggregate evidence boundary for Domain 02
C09-C12. It is the release contract for phased haplotype assembly,
allele-aware structural variation, pangenome interval projection, and
repeat/mobile-element annotation.

The gate is intentionally narrower than a clinical or population-genomics
validation program. It proves that the checked-in adapters preserve declared
inputs, distinguish accepted observations from review controls, carry exact
context and source identity, and expose deterministic sanitized outputs.

## Scope

The gate covers four capability IDs:

| Capability | Operation | Primary boundary |
| --- | --- | --- |
| GNC-D02-C09 | `phased_haplotype` | explicit phased genotype to ordered haplotype paths |
| GNC-D02-C10 | `allele_aware_sv` | structural event to allele/dosage representation |
| GNC-D02-C11 | `pangenome_projection` | interval query to supplied graph paths |
| GNC-D02-C12 | `repeat_mobile_annotation` | interval query to repeat/mobile catalogue hits |

The canonical context has six pipe-delimited fields:

```text
GRCh38|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment
```

The fields are, in order: reference build, disease context, age stratum,
cell/state stratum, specimen region, and treatment phase. The exact string is
part of the fixture identity. A record from another build or another specimen
state is not silently normalized into the canonical context.

## Public source boundary

The fixture uses source receipts rather than private case material. Each
receipt has a stable source ID, title, URL, version, license, scope, retrieval
date, and an aggregate-only flag. The URLs are recorded in the fixture and
are also available for direct review:

- [NCBI dbVar](https://www.ncbi.nlm.nih.gov/dbvar/)
- [dbVar Human Structural Variation Data Hub](https://www.ncbi.nlm.nih.gov/dbvar/content/human_hub/)
- [dbVar Study Browser](https://www.ncbi.nlm.nih.gov/dbvar/studies/)
- [dbVar FTP manifest](https://www.ncbi.nlm.nih.gov/dbvar/content/ftp_manifest/)
- [gnomAD-SV v4 structural variants](https://gnomad.broadinstitute.org/news/2023-11-v4-structural-variants/)

The source receipts frame the local aggregate fixture. They do not claim that
the compact fixture is a complete export of any source, that the sources have
identical release schedules, or that a source row is a patient-level
observation.

## Fixture envelope

The canonical fixture is
`examples/structural-haplotype-public-aggregate.json`.

```json
{
  "schema_version": "structural-haplotype-evidence-v1",
  "fixture_id": "structural-haplotype-public-aggregate-2026-08-21",
  "context_key": "GRCh38|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment",
  "sources": [],
  "positives": [],
  "controls": [],
  "audit": {}
}
```

The real fixture fills `sources`, `positives`, `controls`, and `audit`. The
envelope parser rejects missing IDs, duplicate sources, duplicate record IDs,
invalid URLs, patient-level flags, context strings with the wrong number of
fields, unsupported operation names, and records that do not belong to the
declared source set.

Every operation record contains:

| Field | Rule |
| --- | --- |
| `record_id` | unique within the fixture |
| `operation` | one of the four registered operations |
| `expected_state` | `accepted` for a positive or `review` for a control |
| `expected_result_state` | expected detector state, such as `supported` or `ambiguous` |
| `context_key` | exact six-field context |
| `source_id` | must resolve to a fixture receipt |
| `payload` | non-empty operation input |
| `required_issue_codes` | issue codes required on controls |
| `expected_counts` | count assertions for the operation output |

The payload is executed locally, but it is not copied into published
evaluation receipts, bundles, lineage nodes, quality reports, or pipeline
manifests. This keeps the release surfaces aggregate and reviewable while
allowing the evaluator to prove that the adapters actually ran.

## Positive records

There is one positive record for each operation.

### C09 phased haplotype

The positive includes two explicit phased observations in one phase set. The
expected result is `supported`, with two haplotype paths, zero unphased
observations, and zero issues. The adapter retains allele calls, phase-set
identity, source hashes, and observation ordering.

### C10 allele-aware structural variation

The positive includes one allele-indexed deletion with genotype, phase, dosage,
copy number, and support fields. The expected result is `supported`, with one
represented event and zero issues. The operation keeps dosage and event
identity separate from coordinate-level grouping.

### C11 pangenome projection

The positive includes one bounded query and one matching graph node on an
explicit path. The expected result is `supported`, with one match, zero
unmapped queries, and zero issues. Projection relation labels remain visible.

### C12 repeat/mobile annotation

The positive includes one bounded query and one source-versioned LINE
annotation. The expected result is `supported`, with one hit, zero unannotated
queries, and zero issues. Family, class, subfamily, strand, and mobile status
remain part of the local result.

## Review controls

The fixture has eight controls. Controls are executable negative evidence, not
discarded rows.

| Control | Operation | Expected state | Required condition |
| --- | --- | --- | --- |
| `control-phased-unphased` | C09 | `ambiguous` | unphased genotype remains visible |
| `control-phased-context-drift` | C09 | `out_of_domain` | record context differs from fixture context |
| `control-allele-conflict` | C10 | `contradictory` | same declared event has conflicting observations |
| `control-allele-missing-dosage` | C10 | `partial` | event is retained without dosage |
| `control-pangenome-ambiguous-paths` | C11 | `ambiguous` | query maps to multiple supplied paths |
| `control-pangenome-unmapped` | C11 | `partial` | no supplied graph node covers query |
| `control-repeat-mixed-classes` | C12 | `ambiguous` | overlapping hits have incompatible classes |
| `control-repeat-context-drift` | C12 | `partial` | annotation context is out of domain |

The evaluator requires each control's expected result state, required issue
codes, and operation-specific counts. A control that unexpectedly becomes a
supported positive fails the fixture gate even if no exception occurs.

## Execution layers

The release evidence is calculated in independent layers so that a single
summary cannot hide a broken boundary.

### Data audit

`audit_structural_haplotype_fixture` checks schema version, fixture ID,
context shape, source URL/scope, aggregate-only policy, operation coverage,
positive/control floors, duplicate identities, source membership, and safe
payload keys. The canonical audit has four source receipts, four positives,
eight controls, and no issue codes.

### Fixture evaluation

`evaluate_structural_haplotype_fixture` executes every positive and control
through the existing adapter. It produces twelve operation receipts and 72
checks. Check IDs are record-scoped, for example:

```text
positive-phased-haplotype:state
positive-phased-haplotype:result-state
positive-phased-haplotype:count-haplotypes
control-allele-conflict:issue-conflicting_allele_observation
```

Each receipt includes operation, capability, expected and observed state,
result state, non-negative counts, issue codes, a detail string, and a
content address. It excludes raw records and sequence payloads.

### Contract registry

`default_structural_haplotype_contract_registry` declares four contracts. A
contract states the required input fields, output fields, provenance fields,
accepted result states, review result states, and safety boundary. The quality
gate requires all four contracts to be present and non-empty.

### Replay

`replay_structural_haplotype_fixtures` loads one or more catalog paths and
checks that each replay has the expected fixture ID, exact context, source set,
minimum 40 checks, four positive records, eight controls, unique record and
address identities, and a stable evaluation address. Replay is a second read
of the public fixture contract; it is not a replacement for the operation
checks.

### Scenario matrix

`evaluate_structural_haplotype_scenarios` runs twelve independent cases:

- four supported positives;
- two phased review transitions;
- two allele review transitions;
- two pangenome review transitions;
- two repeat review transitions.

Each scenario requires a result state, fixture state, and issue condition. The
matrix does not reuse the fixture evaluation receipts for its verdict.

### Quality gate

`evaluate_structural_haplotype_quality_gate` reconciles 20 checks:

1. data audit;
2. fixture evaluation;
3. record/check floor;
4. replay identity;
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
15. addressed receipt floor;
16. contract-state coverage;
17. sanitized receipt boundary;
18. lineage audit;
19. lineage node shape;
20. lineage edge shape.

The canonical report is `accepted`, has 20 passing checks, and contains no
failed check IDs.

### Lineage

`build_structural_haplotype_lineage` creates a typed graph with:

- four source nodes;
- one fixture node;
- twelve record nodes;
- twelve result nodes;
- source-to-record `declares` edges;
- fixture-to-record `contains` edges;
- record-to-result `produces` edges.

The expected shape is 29 nodes and 36 edges. The lineage audit recomputes the
graph address from sanitized nodes and edges, checks all endpoints, checks
record/result pairing, checks source coverage, and checks exact context.

## Runtime state machine

`run_structural_haplotype_pipeline` accepts a pipeline request with four
operation payloads and executes them in enum order:

```text
phased_haplotype
        |
allele_aware_sv
        |
pangenome_projection
        |
repeat_mobile_annotation
        |
stage manifest
```

The runtime states are:

- `accepted`: all stages have non-zero input, no issue codes, and valid
  accepted results;
- `review`: at least one stage executed but one or more stages have a review
  state or issue code;
- `blocked`: all stage collections are empty, so no manifest is published.

Stage receipts conserve input counts, expose capability IDs and output
addresses, and omit raw operation payloads. A review report still publishes a
sanitized stage manifest for inspection. A blocked report has no manifest.

## Release commands

```powershell
python -m glio_noncode audit-structural-haplotype-data examples/structural-haplotype-public-aggregate.json --output data.json
python -m glio_noncode evaluate-structural-haplotype-fixture examples/structural-haplotype-public-aggregate.json --output fixture.json
python -m glio_noncode replay-structural-haplotype-fixtures examples/structural-haplotype-public-aggregate.json --output replay.json
python -m glio_noncode evaluate-structural-haplotype-scenarios examples/structural-haplotype-public-aggregate.json --output scenarios.json
python -m glio_noncode structural-haplotype-quality-gate examples/structural-haplotype-public-aggregate.json --output quality.json
python -m glio_noncode build-structural-haplotype-bundle examples/structural-haplotype-public-aggregate.json --output bundle.json
python -m glio_noncode structural-haplotype-lineage examples/structural-haplotype-public-aggregate.json --output lineage.json
python -m glio_noncode run-structural-haplotype-pipeline examples/structural-haplotype-pipeline-accepted.json --output pipeline.json
```

Commands return exit code 0 for their accepted/passed state and exit code 2
for a review or failed gate. The bundle command refuses a failed quality gate
unless `--allow-review` is supplied explicitly.

## Limitations

This gate does not establish:

- read-backed or molecule-backed phase;
- truth-set accuracy for structural variant callers;
- sequence homology across graph paths;
- complete repeat or mobile-element annotation;
- transposition, clonality, pathogenicity, prognosis, or treatment response;
- clinical-grade identity, consent, or specimen authentication;
- equivalence with RefGet, VRS, GA4GH graph interchange, or another external
  validation standard.

Those are separate validation programs. The local gate is complete only for
the explicit aggregate contract described here.
