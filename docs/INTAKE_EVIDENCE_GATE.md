# Domain 01 intake evidence gate

This document describes the evidence boundary for capabilities C13 through
C16 in the checked-in capability ledger:

| Capability | Operation | Core adapter | Verified evidence |
| --- | --- | --- | --- |
| GNC-D01-C13 | `attach-consent-policy` | `ConsentPolicyAttacher` | policy identity, version, purpose, permitted uses, status, expiry, exact context, and block receipts |
| GNC-D01-C14 | `quarantine-input-anomalies` | `InputAnomalyQuarantine` | duplicate identity, context, coordinates, sequence alphabet, source identity, and retained quarantine rows |
| GNC-D01-C15 | `score-data-completeness` | `DataCompletenessScorer` | weighted present/missing/invalid fields, score, threshold, review IDs, and deterministic address |
| GNC-D01-C16 | `export-intake-bundle` | `IntakeBundleExporter` | sorted source IDs, exact context, record address, acceptance gate, manifest, and content address |

The operational code predates this gate.  The gate is the independent layer
that proves those adapters work against public inputs, retain negative controls,
and agree with a declarative contract.  A unit test for a single adapter is not
enough to mark a ledger capability verified.

## Scope and source boundary

The canonical fixture is
`examples/intake-public-aggregate.json`.  It contains four positive operation
records and eight negative controls.  The positive records are bound to this
exact context key:

```text
GRCh38|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment
```

The six fields are always serialized in this order:

1. genome build;
2. disease class;
3. age group;
4. cell state;
5. territory;
6. treatment phase.

The fixture declares four public source receipts:

- the NIH Genomic Data Sharing policy page for the policy attachment path;
- the NCBI ClinVar RCV record `RCV000292094.7` for the public aggregate identity;
- the NCBI GRCh38 reference assembly `GCF_000001405.40` for the reference boundary;
- the repository fixture-control source for intentionally malformed review rows.

Every receipt records a source ID, HTTPS URL, version string, exact context,
public scope, patient-level flag, license label, and source class.  The audit
requires `patient_level_data=false` and rejects a source that is not public.
The source URLs are identifiers and provenance receipts; the package does not
silently fetch network data as part of a local fixture evaluation.

The fixture-level provenance also declares:

```json
{
  "data_scope": "public_policy_and_aggregate",
  "patient_level_data": false,
  "expected_record_count": 4,
  "expected_control_count": 8
}
```

The data boundary does not claim consent validity for a real person, biological
sample authentication, assay quality, clinical interpretation, or permission
to publish a real-world record.  It verifies that declared policy and intake
metadata are preserved and reviewed according to the local contract.

## Fixture shape

The top-level object contains:

```text
schema_version
fixture_id
fixture_version
context
source_receipts[]
records[]
negative_controls[]
expected_negative_control_count
provenance
```

Each positive record contains:

```text
record_id
kind                 # consent | anomaly | completeness | bundle
operation
source_id
context_key
public_identifier
expected_state
payload
```

Each negative control contains the same operation envelope plus:

```text
control_id
required_issue_codes[]
```

The parser keeps controls separate from positive records.  It can project a
control to a record-shaped envelope for execution, but its identity remains
`negative:<control_id>` in the scenario and operation receipts.

## Data audit

`IntakeFixtureCatalog.audit()` performs the following checks before operation
results are considered evidence:

- schema version matches `intake-evidence-v1`;
- at least one source receipt is present;
- every source uses HTTPS and declares public, non-patient-level scope;
- source context keys match the fixture context exactly;
- source IDs are unique;
- positive record IDs and control IDs are unique within their respective sets;
- positive and control identities do not collide;
- every envelope context matches the fixture context;
- every envelope source ID has a receipt;
- nested payload keys do not expose restricted field names;
- provenance explicitly rejects patient-level data;
- provenance names an allowed public scope and an evidence boundary;
- declared positive and control counts match parsed counts;
- a negative control cannot declare `accepted` as its expected state.

The audit never uses a restricted field's value in an issue detail.  It reports
an addressable path such as `records[0].payload.private_note`, allowing the
fixture maintainer to correct the structure without copying sensitive content
into a report.

## Operation contracts

`default_intake_contract_registry()` declares required input fields, output
fields, accepted states, review states, evidence role, and external boundary
for every C13-C16 operation.

### C13 policy attachment

The input payload declares a list of intake rows plus policy identity,
policy version, purpose, and permitted uses.  Each row is evaluated against
the requested context and a simple active-status vocabulary (`granted`,
`active`, or `approved`).  A row with an inactive status or mismatched context
is retained as `blocked`; it is not dropped or rewritten.  The result keeps
accepted and blocked IDs, per-row issues, and a content address.

### C14 anomaly quarantine

The input payload declares rows and an allowed sequence alphabet.  Duplicate
IDs, missing or mismatched context, invalid one-based coordinates, unsupported
bases, and missing source identity become anomaly codes on an observation.
Rows with codes are `quarantined`; clean rows are `accepted`.  Both sets are
retained in the report, so the output can be reconciled with the source row
count.

### C15 completeness scoring

The input payload declares required fields, positive weights, a minimum score,
and rows.  Each score separately records present, missing, and invalid fields.
The threshold is explicit and the mean score is deterministic.  A row with an
invalid coordinate field remains `review` even if its numeric coverage would
otherwise meet the threshold.

### C16 bundle export

The input payload declares a bundle ID, source IDs, rows, and whether accepted
state is required.  The exporter sorts source IDs, computes a records address,
builds a stable manifest, and computes a final content address.  Context
mismatches and blocked/quarantined/review states raise a validation failure
when the acceptance gate is enabled.  The evaluator converts that failure into
a safe `review` receipt for a negative control; it does not treat the failure
as a successful export.

## Executable fixture evaluation

`IntakeFixtureEvaluator` runs all four positive records and all eight controls
through the same adapter dispatch.  The current fixture produces 33 checks:

| Check family | Count | Purpose |
| --- | ---: | --- |
| Data boundary | 1 | the catalog is accepted before operation evidence is used |
| Positive state | 4 | each adapter returns its declared accepted or published state |
| Positive trace | 4 | each public identifier survives in its receipt |
| Positive address | 4 | each adapter result has a content address |
| Negative state | 8 | each review control returns its declared state |
| Negative issue codes | 8 | required reasons remain visible |
| Control floor | 1 | all eight controls executed |
| Determinism | 1 | the first positive operation replays to the same address |
| Output boundary | 1 | restricted output field names are absent |
| Operation kind floor | 1 | all four operation kinds are present |
| **Total** | **33** | |

The positive states are `accepted`, `accepted`, `accepted`, and `published`
for C13, C14, C15, and C16 respectively.  The controls cover withdrawn and
context-mismatched policy, duplicate and invalid-sequence rows, missing and
invalid completeness inputs, and blocked or cross-context bundle exports.

Operation exceptions are represented by `IntakeOperationFailure`.  The failure
receipt contains a stable error code and operation name, not an exception
message that could copy an input value.  This allows the scenario matrix to
assert that a rejected bundle remains reviewable.

## Replay and scenario evidence

`IntakeReplayRunner` checks fixture ID, exact context, source set, check floor,
positive record floor, negative-control floor, accepted fixture state, unique
positive IDs, unique control IDs, and positive/control separation.  Replaying
the same path twice is deliberately rejected as duplicate fixture identity and
duplicate case address; this prevents an accidental duplicate from looking
like independent evidence.

`IntakeScenarioMatrix` independently derives twelve scenarios.  It executes
the operation dispatch again instead of trusting the evaluator's stored
reports.  Four scenarios are positive and eight are review-boundary cases.
Each result records expected state, observed state, required issue codes,
observed issue codes, and a deterministic address.

## Quality gate

`IntakeQualityGate` reconciles the fixture evaluator, data audit, replay,
scenario matrix, and contract registry.  It has fourteen checks:

1. fixture evaluation is accepted;
2. fixture check floor is at least 33;
3. public-data audit is accepted;
4. replay is clean;
5. exactly four positive operation records are present;
6. exactly eight controls are present;
7. exactly twelve scenarios pass;
8. exactly four contracts cover the fixture operations;
9. every positive payload contains its contract fields;
10. fixture, data, and replay context keys agree;
11. fixture, data, and replay source sets agree;
12. repeated evaluation is deterministic;
13. positive public identifiers are unique;
14. quality-gated output contains no restricted field names.

The gate state is `accepted` only when every check passes.  A review state is a
real result and is not coerced to success by a bundle renderer.

## Batch orchestration runtime

The evidence adapters can also be executed through `IntakePipeline`, a typed
four-stage runtime for a batch of public aggregate rows. The request boundary
requires an ID, exact context, policy identity and version, purpose,
permitted uses, source IDs, required fields, positive weights, a completeness
threshold, and at least one uniquely identified record. A missing `source_ids`
array is derived from the record source IDs, but all other required policy and
schema fields remain explicit.

The runtime applies the stages in this order:

1. `GNC-D01-C13` attaches the policy receipt and retains only records with an
   active consent state, a usable expiry, the requested source, and the exact
   context key.
2. `GNC-D01-C14` inspects coordinate, sequence, source, context, and duplicate
   conditions. A malformed row remains addressable through a blocked ID and
   issue code rather than disappearing from the batch.
3. `GNC-D01-C15` calculates weighted field coverage. A row can be review-bound
   for missing or low-scoring fields without being misclassified as an input
   anomaly.
4. `GNC-D01-C16` exports only the intersection of the accepted ID sets. The
   report contains manifest metadata and a content address, while raw record
   payloads are not copied into the published receipt.

Each stage receipt exposes the operation, capability, input count, accepted
count, review count, issue codes, output address, and boundary detail. The
invariant `accepted_count + review_count == input_count` is enforced for every
stage. The aggregate state is `accepted` only when every requested row is in
the exported intersection. If a partial bundle exists, the aggregate state is
`review`; if no row can be exported, it is `blocked`. A row blocked by consent
or anomaly remains blocked, while a row that passes those gates but fails
completeness remains review-bound.

The batch runtime is available from Python and the CLI:

```powershell
python -m glio_noncode run-intake-pipeline examples/intake-pipeline-accepted.json --output intake-pipeline.json
python -m glio_noncode run-intake-pipeline examples/intake-pipeline-batch.json --output intake-pipeline-review.json
```

The accepted fixture is a one-row success case for CI. The batch fixture has a
valid ClinVar-backed row and a deliberately invalid sequence row; it produces
a partial manifest, exposes the blocked row, and exits with status two because
review is not accepted. Re-running either request produces the same report
address and stage addresses.

## Local commands

Run the individual surfaces:

```powershell
python -m glio_noncode audit-intake-data examples/intake-public-aggregate.json --output intake-data.json
python -m glio_noncode evaluate-intake-fixture examples/intake-public-aggregate.json --output intake-fixture.json
python -m glio_noncode replay-intake-fixtures examples/intake-public-aggregate.json --output intake-replay.json
python -m glio_noncode evaluate-intake-scenarios examples/intake-public-aggregate.json --output intake-scenarios.json
python -m glio_noncode intake-contracts --output intake-contracts.json
python -m glio_noncode intake-quality-gate examples/intake-public-aggregate.json --output intake-quality.json
python -m glio_noncode build-intake-bundle examples/intake-public-aggregate.json --output intake-bundle.json
```

The command exits zero for an accepted/passed result and exits two when the
result is review or otherwise fails its declared gate.  `build-intake-bundle`
accepts `--format json`, `--format csv`, or `--format markdown`.  The optional
`--allow-review` flag is intended for inspection of a failed fixture and does
not change the bundle state to accepted.

## Verification checklist

The repository verification surface covers:

- direct catalog and source-boundary tests;
- positive and negative operation execution;
- failure receipt behavior;
- replay floors and drift checks;
- contract lookup and manifest addressing;
- independent scenario state transitions;
- quality-gate mutations for source scope, context, counts, and identities;
- JSON, CSV, and Markdown bundle rendering;
- CLI exit codes and output files;
- Python compilation, full unit tests, and the three-version Actions matrix.

The fixture is evidence for bounded intake mechanics.  It is not a claim that
the source policy has been adjudicated for a specific institution or that the
public ClinVar record is a substitute for a specimen-level consent and quality
record.
