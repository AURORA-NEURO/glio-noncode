# Specimen frontier evidence gate

This document defines the evidence boundary for Domain 03 capabilities C01
through C04:

| Capability | Adapter | Accepted outcome |
| --- | --- | --- |
| GNC-D03-C01 | specimen ontology mapping | `supported` |
| GNC-D03-C02 | matched normal resolution | `supported` |
| GNC-D03-C03 | purity and ploidy import | `accepted` |
| GNC-D03-C04 | contamination and swap detection | `clear` |

The gate is a deterministic, aggregate-data contract. It is intended to make
the mechanics of the four adapters inspectable and repeatable. It is not a
patient registry, a clinical decision system, a specimen identity service, or
a replacement for validation against laboratory materials.

## 1. Scope and source boundary

The checked-in fixture is
`examples/specimen-frontier-public-aggregate.json`. It is a synthetic
aggregate catalog. Each record has a stable record key, a six-field context,
an operation, a pseudonymous subject key, a public-source receipt set, and a
payload appropriate to that operation.

The source receipt set is metadata-shaped. It identifies four public reference
surfaces:

| Receipt ID | Public surface | What it supports |
| --- | --- | --- |
| `ncbi-biosample-docs` | NCBI BioSample documentation | descriptive sample metadata and relationships to derived data |
| `gdc-data-model` | GDC data model | project, case, sample, and read-group entity structure |
| `gdc-data-dictionary` | GDC data dictionary | field and relationship vocabulary for biospecimen records |
| `ena-browser-guides` | ENA browser guides | sample registration and retrieval workflow vocabulary |

The source URLs are retained in the fixture and are not fetched as part of a
normal local evaluation. The evidence gate checks that every record names one
or more declared receipts and that every receipt is in the catalog. The source
receipts provide provenance scope; they do not turn the synthetic rows into
source-derived observations.

The fixture uses the exact context key:

```text
GRCh38|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment
```

The six fields are, in order:

1. reference build;
2. disease or study context;
3. age band;
4. cell or tissue context;
5. collection material;
6. treatment phase.

The context is an equality boundary. A record with a missing field, a changed
field order, or an additional field does not silently join this fixture.

## 2. Aggregate privacy boundary

The catalog accepts pseudonymous keys such as `subject_key`,
`declared_subject_key`, and `observed_subject_key`. It rejects keys that look
like direct identifiers or patient-level identifiers, including:

```text
patient_id
subject_id
medical_record_number
sample_patient_id
participant_id
```

The audit walks nested mappings and sequences, so a sensitive key cannot be
hidden inside a payload, receipt, scenario, or expected-result object. The
audit also rejects an aggregate record that declares a patient-level scope.

This is a structural control, not a privacy certification. A real deployment
must apply its own access, retention, de-identification, and governance
requirements before accepting any data.

## 3. Record schema

Each fixture record contains the following fields:

| Field | Type | Required behavior |
| --- | --- | --- |
| `record_id` | string | unique within the fixture |
| `source_ids` | array of strings | non-empty and drawn from the catalog |
| `context` | object | exact six-field context |
| `operation` | enum | one of the four operation names |
| `state` | enum | `accepted` for positives or `review` for controls |
| `payload` | object | operation-specific aggregate payload |
| `expected` | object | expected state, issues, and counts |
| `content_address` | string | SHA-256 address of the canonical record |

The canonical address is computed from the record without its address field.
JSON objects are sorted by key, arrays retain declared order, and separators
are compact. An address mismatch is a fixture failure even when the payload
would otherwise produce the expected adapter result.

The catalog also carries floors:

```json
{
  "minimum_positive_records": 4,
  "minimum_control_records": 8,
  "minimum_context_dimensions": 6
}
```

The floors prevent a future fixture edit from reducing the negative-control
surface while leaving the release command green.

## 4. Operation contracts

### C01 ontology mapping

The positive row has one specimen row, one explicit aggregate subject key, one
sample type, and one tissue label. The adapter maps it to a stable ontology
candidate. The result retains mapping confidence and the source row index.

The controls cover two different failures:

- conflicting subject keys in one specimen row;
- a row with no usable sample identifier.

Both controls must preserve structured issue codes. A control is not counted as
handled if the adapter converts missing values into the string `None`, drops
the row without a receipt, or chooses one conflicting key arbitrarily.

### C02 matched normal resolution

The positive row names a tumor and exactly one normal for the same aggregate
subject key. The resolver returns a pair with explicit relationship evidence.

The controls cover:

- a subject with multiple declared normal samples;
- a subject with no normal sample.

The resolver does not infer a match from ordering, sample-name similarity, or
an unrelated subject key. Missing and multiple relationships remain review
states.

### C03 purity and ploidy import

The positive row contains a valid purity percentage and a valid ploidy value.
The importer normalizes percentage input to a unit interval while retaining
the original representation and caller receipt.

The controls include a malformed value and an out-of-range value. The importer
keeps the malformed row count and the issue code. It does not clamp invalid
values into an accepted measurement. The aggregate fixture contains no raw
measurement files and makes no claim about assay calibration.

### C04 contamination and swap detection

The positive row contains a complete declared/observed fingerprint summary
with matching subject keys and no contamination signal. The detector reports
`clear` only for this complete agreement.

The controls cover:

- a declared subject mismatch;
- a contamination signal above the declared threshold;
- incomplete fingerprint metrics.

Incomplete metrics must abstain or enter review. They must not be treated as a
clean match because missing evidence is not negative evidence.

## 5. Evaluation pipeline

`SpecimenFrontierFixtureEvaluator` processes records in declared order and
emits an execution object for each record. Every execution has:

- fixture and record identity;
- operation and fixture state;
- result state;
- issue codes and issue severities;
- expected and observed counts;
- input and output content addresses;
- sanitized output fields.

The evaluator performs six checks per record:

1. fixture state agrees with the expected state;
2. adapter result state agrees with the expected state;
3. issue codes agree as a set;
4. operation-specific counts agree;
5. the record address agrees;
6. the output contains no sensitive keys.

The canonical catalog therefore has 12 records and 72 checks. The evaluator
reports positive and control counts separately so a fixture with only positive
examples cannot satisfy the gate.

The evaluator does not use random sampling, time, network calls, ambient
environment variables, or external model state. Repeating the command against
the same file produces the same report address and check ordering.

## 6. Scenario matrix

The scenario matrix is independent of the record evaluator. It declares one
scenario for each positive and control behavior and compares the observed
operation result with the scenario expectation.

The 12 scenarios are:

| Operation | Positive | Controls |
| --- | --- | --- |
| ontology mapping | one supported mapping | conflicting subject, missing sample |
| matched normal | unique pair | multiple normals, missing normal |
| purity/ploidy | valid measurements | malformed row, invalid value |
| sample integrity | clear match | subject mismatch, contamination, incomplete metrics |

The independent matrix catches accidental coupling between fixture evaluation
and scenario expectations. It also ensures each operation has both a success
path and a review path.

## 7. Replay contract

`replay_specimen_frontier_fixture` verifies the following before reporting
success:

- the fixture ID is the expected fixture ID;
- the exact context string is unchanged;
- every source receipt ID is present and ordered deterministically;
- the positive and control floors are unchanged;
- the fixture has no duplicate record IDs;
- the fixture has no duplicate content addresses;
- the data audit passes;
- the fixture evaluation passes.

Replay is intentionally stricter than a smoke test. Changing a source URL,
record address, context dimension, expected issue, or control count is a
reviewable change that should fail replay until the expectation is updated
deliberately.

## 8. Quality gate

The quality gate combines the independent reports into 21 checks:

| Check group | Required property |
| --- | --- |
| data boundary | source receipts, exact context, aggregate scope, and address integrity |
| execution | all fixture checks pass and all four operations are present |
| replay | identity, source, floor, and deterministic evaluation agreement |
| scenarios | 12 independent scenarios pass |
| contracts | four operation contracts are present with positive and review states |
| lineage | source, fixture, record, and result nodes are address-consistent |
| output boundary | sanitized execution, receipt identity, and no raw sensitive keys |
| controls | positive/control floors and issue coverage pass |

The quality report includes check IDs, pass/fail state, observed values, and a
short failure reason. It does not include raw payloads in the compact report.
The CLI returns a non-zero status for a failed quality gate.

## 9. Bundle and lineage release rules

The evidence bundle builder accepts the catalog only after its aggregate audit
and fixture evaluation pass. An accepted bundle contains 12 entries. A review
bundle requires the explicit `--allow-review` option and preserves the review
state in every entry.

The lineage graph has four source nodes, one fixture node, 12 record nodes,
and 12 result nodes. Its 36 edges use three relations:

- `declares`: source or fixture declaration;
- `contains`: fixture-to-record membership;
- `produces`: record-to-result execution.

The lineage audit checks endpoint existence, relation vocabulary, node address,
record/result pairing, source coverage, and exact context. It is a provenance
graph for the evidence run, not a biological ancestry graph.

## 10. Runtime integration

The runtime composes the four operations in this order:

```text
ontology_mapping -> matched_normal -> purity_ploidy -> sample_integrity
```

Each stage emits a receipt with input count, accepted count, review count,
blocked count, issue codes, and a deterministic stage address. Stage counts
are conserved. The final manifest contains only sanitized record IDs and
states.

The accepted pipeline fixture reaches `accepted` and `published`. The review
pipeline fixture reaches `review` and retains issue codes in the manifest. A
blocked stage prevents publication and stops later stages from being presented
as successful.

## 11. Local verification

Run the complete evidence gate with:

```powershell
python -m glio_noncode audit-specimen-frontier-data examples/specimen-frontier-public-aggregate.json --output specimen-data.json
python -m glio_noncode evaluate-specimen-frontier-fixture examples/specimen-frontier-public-aggregate.json --output specimen-fixture.json
python -m glio_noncode specimen-frontier-quality-gate examples/specimen-frontier-public-aggregate.json --output specimen-quality.json
python -m glio_noncode specimen-frontier-lineage examples/specimen-frontier-public-aggregate.json --output specimen-lineage.json
python -m glio_noncode run-specimen-frontier-pipeline examples/specimen-frontier-pipeline-accepted.json --output specimen-pipeline.json
```

The focused test modules cover the catalog, evaluator, contracts, replay,
scenarios, quality gate, bundle, lineage, runtime, and CLI. The repository
workflow runs the same commands on the supported Python matrix.

## 12. Limitations

This gate proves deterministic software behavior at the declared aggregate
boundary. It does not prove that a source receipt is complete, that a sample
label is biologically correct, that a fingerprint algorithm is calibrated, or
that purity/ploidy values are fit for a clinical decision. Those questions
require independent validation, appropriate consent and governance, laboratory
quality controls, and domain review.

Any future expansion to patient-level data, external credentials, live source
retrieval, or clinical reporting requires a new data boundary and a new review
of the schemas, controls, and release policy.
