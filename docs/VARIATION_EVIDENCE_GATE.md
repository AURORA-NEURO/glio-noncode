# Domain 01 variation evidence gate

This runbook describes the executable evidence boundary for the deeper Domain
01 variation adapters. It is written for maintainers who need to extend the
module family without weakening source accounting, exact context, abstention,
or reproducibility behavior.

## Boundary statement

The checked-in fixture is `examples/variation-public-aggregate.json`. It uses
public aggregate identifiers and a bounded sequence window. It has no
patient-level records. A green gate proves that the local software contracts
produce the declared states for those inputs. It does not prove a biological
effect, clinical interpretation, treatment response, or transfer to a different
reference or cohort.

The fixture deliberately uses a source receipt from NCBI ClinVar and a source
receipt for the GRCh38 assembly. Source URLs identify the public records used to
anchor the fixture. The computational sequence window is retained as a bounded
reproducibility input, not as a patient observation.

The evidence boundary is carried in the fixture and every aggregate report:

> public aggregate identity and deterministic software receipts only; no
> biological or clinical claim

Do not replace this sentence with a stronger claim without adding an external
validation protocol and a separate review decision.

## Module map

The variation slice has five executable adapters and four evidence layers.

| Layer | Module | Responsibility |
| --- | --- | --- |
| Adapter | `variant_normalization.VRSNormalizer` | Normalize literal SNVs/indels and emit a VRS-shaped allele. |
| Adapter | `variant_beta.CategoricalCatalogParser` | Parse versioned declared categorical definitions. |
| Adapter | `variant_beta.CatVRSNormalizer` | Match only declared IDs, aliases, terms, and members. |
| Adapter | `variant_beta.VAAnnotationEnvelopeBuilder` | Bind statements to subject, context, methods, and evidence lines. |
| Adapter | `variant_beta.MultiAllelicDecomposer` | Create indexed child identities while retaining the parent hash. |
| Adapter | `variant_beta.RepeatAwareNormalizer` | Replay literal edits within a supplied local reference window. |
| Boundary | `variation_public_data.py` | Audit public scope, source receipts, context, IDs, and restricted keys. |
| Evidence | `variation_fixture_eval.py` | Execute positive records and negative controls through the adapters. |
| Evidence | `variation_scenario_matrix.py` | Independently replay each state transition. |
| Evidence | `variation_replay.py` | Enforce identity, context, source, and evidence-floor replay. |
| Evidence | `variation_quality_gate.py` | Reconcile all component receipts into one verdict. |
| Contract | `variation_contracts.py` | Declare required fields, outputs, states, and capability mapping. |
| Export | `variation_bundle.py` | Publish compact JSON, CSV, or Markdown evidence summaries. |

The fixture evaluator and scenario matrix intentionally execute the adapter
path separately. A single aggregate output is not sufficient evidence when the
same adapter could be bypassed by the fixture harness.

## Contract inventory

The declarative contract registry has five contracts. Every positive fixture
record maps to exactly one operation and one capability ID.

| Operation | Record kind | Capability | Accepted state(s) | Review state(s) |
| --- | --- | --- | --- | --- |
| `vrs-normalization` | `vrs` | GNC-D01-C04 | `supported` | `ambiguous`, `abstained`, `invalid` |
| `categorical-normalization` | `categorical` | GNC-D01-C05 | `supported` | `ambiguous`, `abstained`, `invalid` |
| `annotation-envelope` | `annotation` | GNC-D01-C06 | `supported` | `partial`, `abstained`, `contradictory`, `out_of_domain`, `missing` |
| `multiallelic-decomposition` | `multiallelic` | GNC-D01-C07 | `supported` | `partial`, `abstained`, `invalid` |
| `repeat-aware-normalization` | `repeat` | GNC-D01-C08 | `supported`, `ambiguous` | `abstained`, `invalid` |

The registry is intentionally stricter than a serializer. Required fields are
declared before an operation runs, output fields identify the minimum receipt
surface, and accepted/review states are disjoint. A new operation requires a
new contract, a fixture record, a scenario, a targeted test, and a CI command.

Inspect the contract inventory:

```powershell
python -m glio_noncode variation-contracts --output variation-contracts.json
```

The manifest contains a stable address. Its `contract_count` must remain five
until the fixture and this runbook are intentionally extended.

## Fixture schema

The fixture has these top-level fields:

| Field | Required behavior |
| --- | --- |
| `fixture_id` | Stable identity used by replay and duplicate detection. |
| `fixture_version` | Must be `variation-evidence-v1`. |
| `provenance` | Declares source class, license, data scope, numeric-value scope, and evidence boundary. |
| `context` | Six exact dimensions joined into one context key. |
| `source_receipts` | HTTPS public aggregate receipts with license and scope flags. |
| `records` | One positive record per contract kind. |
| `negative_controls` | One expected review or abstention case per boundary family. |
| `expected_negative_control_count` | Evidence-floor count for declared controls. |

The context key is ordered as:

```text
genome_build|disease_class|age_group|cell_state|territory|treatment_phase
```

Every source receipt and positive record must carry the same key. An operation
may retain an inner statement context for a negative control, but the envelope
context remains the fixture context so the mismatch is observable.

## Positive records

The five positive records are intentionally narrow and source-accounted.

### VRS-shaped normalization

The public aggregate identifier `dbsnp:rs121913502` is normalized as a literal
reference/alternate record. The receipt includes:

- normalized chromosome, coordinate, reference, and alternate;
- a VRS-shaped `Allele` and `SequenceLocation` object;
- a local sequence ID when no true digest is supplied;
- input hash and output content address;
- an explicit warning that repeat-aware left alignment was not attempted without
  a reference sequence.

The fixture does not convert the local sequence ID into a RefGet digest. A
future digest-backed fixture must supply a real digest and a truth-set check.

### Categorical variation

The catalog definition contains one declared member ID and a fixed source
version. Matching succeeds because the query contains the declared member
identifier. The match basis must name `declared_member_variation_id`.

The adapter must not infer category membership from a label. The negative
label-only control therefore remains `abstained` with
`category_not_resolved`.

### Annotation envelope

The annotation record has one statement and one evidence line. The statement
references the public aggregate subject and the evidence line references the
NCBI source receipt. The envelope retains method, source version, raw hash,
subject, context, and state.

The object is a fixture term describing source-index presence. It is not a
biological consequence, diagnosis, or treatment recommendation.

### Multi-allelic decomposition

The parent record carries two literal alternates and a `1/2` genotype. The
decomposer emits two child records, each with:

- an indexed allele identity;
- the original alternate;
- parent input hash;
- source ID and source version;
- allele-specific genotype projection;
- no inferred phase or clinical significance.

The symbolic alternate control has no children and retains an
`invalid_alternate` issue. It must not be flattened into a literal allele.

### Repeat-aware normalization

The bounded reference window contains a repeated base. The literal insertion
replays to multiple equivalent positions, so the state is `ambiguous` and no
placement is selected. Each placement retains the edited-window hash, local
window hash, shift, and equivalence basis.

The mismatch control returns `abstained` with `reference_mismatch`. A caller
must repair or replace the reference window before treating the result as
supported.

## Negative-control matrix

The matrix is part of the contract, not optional test decoration.

| Control | Adapter | Expected state | Required reason |
| --- | --- | --- | --- |
| `vrs-symbolic-breakend` | VRS | `abstained` | Unsupported structural class remains visible. |
| `categorical-label-only` | Categorical | `abstained` | `category_not_resolved`. |
| `annotation-context-mismatch` | Annotation | `out_of_domain` | Inner statement context differs. |
| `multiallelic-symbolic` | Decomposition | `abstained` | `invalid_alternate`. |
| `repeat-reference-mismatch` | Repeat | `abstained` | `reference_mismatch`. |

If a negative control begins returning `supported`, the build must fail even if
all positive records still pass. Changing an expected state to hide the failure
is not an acceptable repair.

## Data audit

Run the public-data boundary first when a fixture changes:

```powershell
python -m glio_noncode audit-variation-data examples/variation-public-aggregate.json
```

The audit checks:

1. fixture version;
2. source receipt presence and unique IDs;
3. HTTPS source URLs;
4. public aggregate flags;
5. patient-level scope flags;
6. exact source context;
7. duplicate record IDs;
8. record/source join integrity;
9. exact record context;
10. restricted key paths in record payloads;
11. explicit `patient_level_data=false` provenance;
12. explicit evidence boundary.

The audit reports paths and issue codes, not restricted values. Operational
allele subject IDs are allowed because they identify public aggregate records;
patient, participant, donor, medical-record, contact, credential, and secret
field names are not allowed.

## Fixture evaluation

Run the complete operation fixture:

```powershell
python -m glio_noncode evaluate-variation-fixture examples/variation-public-aggregate.json
```

The evaluator currently emits 29 checks:

- one public-data boundary check;
- three checks for each of five positive records: state, identity trace, and
  content address;
- two checks for each of five negative controls: state and required issues;
- one negative-control count floor;
- one repeated-evaluation determinism check;
- one restricted-output check.

The report stores operation receipts because they are useful for local triage,
but the compact bundle intentionally stores only summaries and entry addresses.

## Scenario matrix

Run the independent state-transition matrix:

```powershell
python -m glio_noncode evaluate-variation-scenarios examples/variation-public-aggregate.json
```

The matrix derives ten scenarios: five positive and five review. It invokes
the adapter path directly and compares the observed state and required issue
codes to the declared scenario. It does not reuse the evaluator's aggregate
check results. This makes a harness bypass visible.

The scenario report is accepted only when every result passes. Its result-level
addresses allow a maintainer to identify the exact transition that changed.

## Replay integrity

Replay enforces stable fixture identity across files:

```powershell
python -m glio_noncode replay-variation-fixtures \
  examples/variation-public-aggregate.json \
  --required-context-key "GRCh38|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment"
```

Replay rejects duplicate fixture IDs, mixed contexts by default, missing
required context, failed fixtures, wrong source sets, wrong expected state, and
insufficient check counts. A batch can explicitly allow mixed contexts for a
comparative task, but the caller then owns the interpretation of cross-context
results.

## Combined quality gate

The quality gate reconciles five layers:

1. fixture evaluation;
2. public-data audit;
3. replay integrity;
4. independent scenario matrix;
5. declarative contract inventory.

It currently has twelve checks:

| ID | Requirement |
| --- | --- |
| `fixture-evaluation` | All declared operation and control checks pass. |
| `fixture-check-floor` | At least 29 fixture checks exist. |
| `public-data-audit` | Data boundary is accepted. |
| `replay-integrity` | Identity, context, sources, state, and floor replay cleanly. |
| `record-count` | Five record kinds cover the five adapters. |
| `negative-control-count` | Five review controls remain visible. |
| `scenario-matrix` | Ten independent transitions pass. |
| `contract-inventory` | Five contracts exactly cover the positive operations. |
| `context-consistency` | All components use one context key. |
| `source-consistency` | All components use one source set. |
| `deterministic-evaluation` | Repeated evaluation shares one address. |
| `output-boundary` | Serialized output has no restricted fields. |

Run it in the same form as Actions:

```powershell
python -m glio_noncode variation-quality-gate \
  examples/variation-public-aggregate.json \
  --output variation-quality.json
```

The command returns zero only for an accepted report. It writes a review report
before returning two for a failed fixture, allowing CI artifacts and local
debugging to use the same evidence.

## Bundle export

The bundle exporter is a publication boundary for compact results:

```powershell
python -m glio_noncode build-variation-bundle \
  examples/variation-public-aggregate.json \
  --output variation-bundle.json
python -m glio_noncode build-variation-bundle \
  examples/variation-public-aggregate.json \
  --output variation-bundle.md \
  --format markdown
```

JSON includes summaries, contract manifest, source IDs, context, ten compact
entries, and the content address. CSV contains one row per entry. Markdown is
for human review and includes the evidence boundary. None of these bundle
formats contains raw reference-window sequence, statement bodies, or evidence
line payloads.

## Failure triage

Use the first failed layer rather than editing downstream expected values.

| Failure | First action |
| --- | --- |
| Data audit | Inspect `issues`, `sensitive_paths`, and source/context IDs. |
| Positive state | Run the corresponding base command and inspect its receipt. |
| Negative state | Confirm the control input was not accidentally made literal or in-context. |
| Scenario matrix | Compare the failed scenario result and issue-code set. |
| Contract inventory | Inspect `variation-contracts` and operation names in the fixture. |
| Replay | Check fixture ID, required context, source set, and evidence floor. |
| Determinism | Search for timestamps, unordered collections, or implicit defaults. |
| Output boundary | Remove raw values from serializers and retain only paths or hashes. |

Never fix a mismatch by dropping the failed record. Missing records are a
fixture-shape failure and must remain visible.

## CI order

Actions runs the following sequence after package installation:

1. compile source and tests;
2. run the complete unittest suite;
3. run the existing contract and case checks;
4. audit variation data;
5. evaluate the variation fixture;
6. replay the variation fixture;
7. run the variation scenario matrix;
8. inspect variation contracts;
9. build the variation evidence bundle;
10. run the combined variation quality gate.

Every command writes to a temporary runner path. The fixture itself remains
checked in and is not generated during CI.

## Promotion rule

The ledger marks C04-C08 verified for this bounded software evidence slice only
when all of the following are true:

- the adapter implementation is present;
- targeted unit and CLI tests pass;
- the public aggregate fixture passes data audit;
- positive and negative states pass;
- the scenario matrix passes independently;
- operation contracts map one-to-one to fixture kinds;
- replay preserves identity, context, source set, and check floor;
- the quality gate passes in local validation and Actions.

This promotion does not remove the external gates named in the capability
ledger. RefGet truth sets, external Cat-VRS schema validation, VA-Spec
interchange validation, global repeat equivalence, and structural variant
normalization remain future work.

## Extension checklist

When adding another variation record or adapter:

1. add a public source receipt or reuse an explicitly valid receipt;
2. declare the exact context key;
3. add a contract with required fields and state classes;
4. add a positive record with a stable public identifier;
5. add at least one review control;
6. add a scenario matrix assertion;
7. add targeted unit and CLI tests;
8. add the operation to the quality-gate floor;
9. update this runbook and the capability ledger;
10. run the complete suite before committing.

An extension is not complete when its class can be imported. It is complete for
this evidence boundary when its public input, source receipt, output receipt,
negative control, replay path, and CI command all agree.
