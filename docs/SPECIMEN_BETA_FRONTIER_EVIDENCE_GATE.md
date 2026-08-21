# Specimen beta frontier evidence gate

This document defines the evidence boundary for Domain 03 capabilities C05
through C08:

| Capability | Adapter | Positive result |
| --- | --- | --- |
| GNC-D03-C05 | somatic/germline origin classifier | `supported` |
| GNC-D03-C06 | mosaicism posterior-shaped estimator | `supported` |
| GNC-D03-C07 | cancer-cell fraction estimator | `supported` |
| GNC-D03-C08 | relative subclone assigner | `supported` |

The gate is a deterministic aggregate-data contract. It makes the mechanics of
variant-origin and clonality measurements inspectable. It does not establish a
patient diagnosis, specimen identity, constitutional status, calibrated
clinical probability, or biological tumor phylogeny.

## 1. Source boundary

The checked-in fixture is
`examples/specimen-beta-frontier-public-aggregate.json`. It contains 12
synthetic aggregate records: four positive operation records and eight review
controls. Every record has a stable ID, an exact six-field context, one or more
public source receipt IDs, a payload, an expected state, expected issue codes,
expected counts, and a deterministic content address.

The source receipt set is metadata-shaped and points to public documentation:

| Receipt | Public documentation | Boundary role |
| --- | --- | --- |
| `ncbi-clinvar-classification` | [ClinVar classification representation](https://www.ncbi.nlm.nih.gov/clinvar/docs/clinsig/) | germline, somatic clinical-impact, and oncogenicity vocabulary |
| `ncbi-clinvar-submission` | [ClinVar submission spreadsheets](https://www.ncbi.nlm.nih.gov/clinvar/docs/spreadsheet/) | allele-origin and aggregate-observation fields |
| `gdc-vcf-format` | [GDC VCF format](https://docs.gdc.cancer.gov/Data/File_Formats/VCF_Format/) | tumor/normal sample structure, VAF, depth, and alternate reads |
| `gdc-wgs-cnv` | [GDC DNA sequencing pipelines](https://docs.gdc.cancer.gov/Data/Bioinformatics_Pipelines/DNA_Seq_WGS/) | variant-calling and copy-number workflow vocabulary |

The source URLs are stored as receipts and are not fetched during ordinary
local evaluation. A receipt identifies the public source surface used to shape
the contract; it does not claim that the documentation page contains the
synthetic fixture rows.

The fixture context is:

```text
GRCh38|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment
```

Its six equality-bound dimensions are reference build, disease or study
context, age band, cell or tissue context, collection material, and treatment
phase. A record with a missing, reordered, or changed dimension does not join
the fixture.

## 2. Aggregate-only policy

The fixture accepts aggregate pseudonymous values such as
`aggregate-tumor-a`, `aggregate-blood`, and `aggregate-skin`. It rejects direct
or patient-level key names recursively, including:

```text
patient_id
subject_id
medical_record_number
sample_patient_id
participant_id
case_uuid
individual_id
```

The recursive scan covers source attributes, parameters, expected values, and
nested operation rows. The catalog also rejects a source receipt marked as
patient-level or a fixture marked as non-aggregate.

This is a structural boundary, not a privacy certification. Any deployment
using real case-level material requires separate access, retention,
de-identification, consent, and governance review.

## 3. Record contract

Each record contains:

| Field | Required behavior |
| --- | --- |
| `record_id` | unique within the catalog |
| `operation` | one of `origin`, `mosaicism`, `cancer_cell_fraction`, `subclone` |
| `source_ids` | non-empty and declared in the source receipt set |
| `context_key` | exact match to the catalog context |
| `expected_fixture_state` | `accepted` for positives or `review` for controls |
| `expected_result_state` | adapter result state expected for that row |
| `payload` | operation-specific aggregate rows |
| `parameters` | optional declared threshold overrides |
| `expected_issue_codes` | sorted issue-code expectation |
| `expected_counts` | operation-specific count expectation |
| `content_address` | SHA-256 address of the canonical record body |

The record address excludes only the address field itself. It includes the
operation, context, source IDs, expected state, expected issue codes, expected
counts, parameters, and payload. A changed value therefore requires a new
address and a deliberate replay update.

## 4. C05 origin classification

The origin adapter consumes rows with variant ID, relationship, tumor allele
fraction, normal allele fraction, normal presence, normal alternate reads,
normal depth, and optional population frequency.

The positive record has one tumor observation absent from normal tissue and one
normal observation present in normal tissue. It produces one somatic and one
germline classification. The adapter retains separate evidence channels:

- normal presence;
- normal absence;
- tumor alternate fraction;
- zero alternate reads in a covered normal;
- declared population frequency.

The first control supplies conflicting tumor and normal evidence for one
observation. The result is `ambiguous` with `uncertain` origin and a retained
conflicting observation ID. The second control supplies a malformed fraction;
the result abstains and records `invalid_origin_fraction`.

The classifier does not use a hidden population prior and does not convert a
ClinVar classification vocabulary into a clinical decision. A source receipt
is not evidence that a particular aggregate row was present in that source.

## 5. C06 mosaicism evidence

The mosaicism adapter groups observations by variant ID and distinct tissue
ID. It identifies low-fraction observations below the declared maximum,
records recurrence across tissues, applies a visible contamination penalty,
and emits a posterior-shaped value.

The positive record has three distinct aggregate tissues with low fractions.
It reaches `supported`, retains all three tissue IDs and observation IDs, and
remains `calibrated: false` because no calibration identifier is declared.

The controls cover one-tissue evidence and one-tissue evidence with a
contamination fraction above threshold. Both remain `partial`; the latter
retains its contamination flag and warning. The estimator does not treat a
single tissue as repeated mosaic recurrence, and it does not interpret a
posterior-shaped value as a population-calibrated posterior when no
calibration artifact is supplied.

## 6. C07 cancer-cell fraction

The CCF adapter uses a transparent model with purity, VAF, total copy number,
alternate copy number, and optional depth and alternate-read counts. It
retains the raw CCF calculation beside the reported estimate and optional
binomial interval.

The positive record contains a clonal and a subclonal aggregate observation.
Both remain within the model range and are supported. The out-of-range control
retains its raw calculation, returns no clamped estimate, and becomes
`partial`. The zero-purity control returns an abstained item because the model
has no valid denominator; its batch state is `partial` because a measurement
row exists but cannot be estimated.

The adapter does not silently clamp an invalid result into `[0, 1]`. Depth and
alternate-read inconsistencies remain warnings and do not become evidence of a
biological mechanism.

## 7. C08 relative subclone assignment

The subclone adapter groups CCF observations by aggregate sample ID, performs
deterministic single-linkage clustering in descending CCF order, sorts clusters
by mean CCF, and assigns stable relative IDs.

The positive record has five observations forming two relative clusters. The
boundary control changes the declared ambiguity margin so two observations
near the cluster boundary remain `ambiguous`. The invalid-row control retains
one valid assignment and quarantines an out-of-range CCF with
`invalid_subclone_record`.

Relative IDs are deliberately scoped to the sample and run. They do not name
biological clones, imply mutation order, infer a phylogenetic tree, or assert
evolutionary lineage.

## 8. Fixture evaluation

`SpecimenBetaFrontierFixtureEvaluator` executes records in fixture order and
emits one sanitized receipt per record. Each receipt has six checks:

1. fixture state uses the declared accepted/review vocabulary;
2. observed result state equals the expected result state;
3. observed issue codes equal the expected set;
4. observed operation counts equal the expected counts;
5. record, input, and output addresses are present;
6. sanitized output contains no raw `records` collection or sensitive keys.

Twelve records times six checks yields 72 checks. Positive and control counts
remain separate. The evaluator has no random sampling, network dependency,
clock dependency, or ambient configuration input.

The compact output includes state summaries, aggregate IDs, issue codes, raw
hashes where the adapter provides them, and content addresses. It does not
copy the operation payload or the adapter issue `raw_record` field.

## 9. Scenario matrix

The scenario matrix executes the same declared records as independent state
scenarios and compares result state plus issue codes. It contains four positive
scenarios and eight controls:

| Operation | Positive | Controls |
| --- | --- | --- |
| origin | separate somatic/germline channels | conflicting evidence, invalid fraction |
| mosaicism | three-tissue recurrence | one tissue, contamination |
| CCF | two valid model estimates | out of range, zero purity |
| subclone | two relative clusters | boundary ambiguity, invalid row |

Mutating an expected state or issue code causes the matrix to fail even if the
fixture evaluator has not been invoked.

## 10. Replay contract

Replay expects the fixture ID, exact context, sorted source set, minimum 72
checks, four positive records, and eight controls. It rejects:

- fixture identity drift;
- context drift;
- source receipt drift;
- reduced check or control floors;
- duplicate record IDs;
- duplicate output addresses;
- data-audit failure;
- fixture-evaluation failure.

Replay is stricter than a smoke test. A source URL or expected-count change is
an evidence change and must be addressed deliberately.

## 11. Quality gate

The quality gate combines 21 checks:

| Group | Checks |
| --- | --- |
| source and scope | data audit, context agreement, source agreement, aggregate scope |
| execution | fixture evaluation, check floor, deterministic evaluation, address floor |
| release identity | replay identity, fixture identity, receipt identity |
| coverage | positive floor, control floor, operation coverage, control-state coverage |
| contracts | contract floor and expected-state coverage |
| output | sanitized boundary |
| provenance | lineage audit and lineage shape |
| scenarios | independent scenario matrix |

The quality report contains check IDs, observed values, expected values, and
failure reasons. It contains no raw operation payload. A failed gate is a
review state and the CLI returns a non-zero status.

## 12. Lineage graph

The lineage graph has:

```text
4 source nodes
1 fixture node
12 record nodes
12 result nodes
36 typed edges
```

Each record has one source-to-record `declares` edge, one fixture-to-record
`contains` edge, and one record-to-result `produces` edge. The audit checks
unique node and edge IDs, endpoint existence, relation vocabulary, exact
context, node shape, source coverage, and graph address.

This graph is evidence-run provenance. It is not a specimen lineage, clonal
ancestry graph, or patient relationship graph.

## 13. Runtime

The runtime stages are fixed:

```text
origin -> mosaicism -> cancer_cell_fraction -> subclone
```

Each stage emits input, accepted, review, and blocked counts that conserve the
stage population. Accepted positive outputs publish a sanitized manifest. A
review stage keeps issue codes and prevents publication. The accepted example
at `examples/specimen-beta-frontier-pipeline-accepted.json` publishes all four
stages; the review example demonstrates state propagation.

## 14. Local commands

```powershell
python -m glio_noncode audit-specimen-beta-frontier-data examples/specimen-beta-frontier-public-aggregate.json --output beta-data.json
python -m glio_noncode evaluate-specimen-beta-frontier-fixture examples/specimen-beta-frontier-public-aggregate.json --output beta-fixture.json
python -m glio_noncode replay-specimen-beta-frontier-fixtures examples/specimen-beta-frontier-public-aggregate.json --output beta-replay.json
python -m glio_noncode specimen-beta-frontier-quality-gate examples/specimen-beta-frontier-public-aggregate.json --output beta-quality.json
python -m glio_noncode specimen-beta-frontier-lineage examples/specimen-beta-frontier-public-aggregate.json --output beta-lineage.json
python -m glio_noncode run-specimen-beta-frontier-pipeline examples/specimen-beta-frontier-pipeline-accepted.json --output beta-pipeline.json
```

## 15. Limitations

This gate proves deterministic software behavior against synthetic aggregate
records shaped by public documentation. It does not establish source
completeness, assay calibration, variant pathogenicity, constitutional status,
contamination cause, CCF clinical validity, or clonal evolution.

Any future expansion to patient-level records, live source retrieval, external
credentials, or clinical reporting requires a new data boundary, schema
review, threat review, and evidence policy.
