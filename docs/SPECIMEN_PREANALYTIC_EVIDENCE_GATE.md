# Specimen preanalytic C13-C16 evidence gate

This document defines the public aggregate evidence boundary for Domain 03
C13-C16. The code surface wraps four bounded operations that already exist in
the data foundation and gives them a common release contract:

1. preanalytic quality threshold assessment;
2. assay and protocol lineage tracking;
3. identity-conflict adjudication; and
4. specimen-context envelope publication.

The evidence gate does not turn these operations into clinical conclusions. It
proves that a checked-in aggregate fixture was parsed, executed, checked,
replayed, reconciled, bundled, and composed through a four-stage runtime while
preserving review states and source scope.

## Release boundary

The checked-in fixture is
`examples/specimen-preanalytic-public-aggregate.json`. It has one exact
context key:

```text
GRCh38|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment
```

The fixture contains twelve aggregate records:

| Operation | Positive | Review controls | Primary boundary |
| --- | ---: | ---: | --- |
| C13 preanalytic quality | 1 | 2 | threshold failure and missing metric retention |
| C14 assay lineage | 1 | 2 | missing parent and duplicate node retention |
| C15 identity adjudication | 1 | 2 | tie and conflicting observation retention |
| C16 context envelope | 1 | 2 | missing receipt and context drift rejection |

The source manifest contains four public receipts. The receipts provide field
vocabulary and scope only:

| Source ID | Scope |
| --- | --- |
| `nci-biospecimen-best-practices` | ischemia, preservation, processing, and storage variables |
| `gdc-biospecimen-data-model` | sample, portion, analyte, aliquot, and processing relationships |
| `gdc-biospecimen-submission` | tissue type, tumor descriptor, specimen type, preservation vocabulary |
| `nci-bbrb-quality-control` | recording times, personnel, processing, storage, and transport controls |

The source URIs are checked in the fixture and are not fetched during test
execution. The source receipts are a reproducibility declaration, not a claim
that the synthetic rows were copied from the source pages.

## Data model

The catalog envelope contains:

| Field | Requirement |
| --- | --- |
| `fixture_id` | stable aggregate fixture identity |
| `fixture_version` | `specimen-preanalytic-public-aggregate-v1` |
| `context_key` | six non-empty pipe-delimited context components |
| `source_receipts` | at least four HTTPS, non-patient-level receipts |
| `records` | exactly twelve operation records |

Each source receipt contains an ID, title, HTTPS URI, scope, an explicit
`patient_level: false` boundary, access date, and a deterministic content
address. A source receipt is invalid if it is missing an ID, uses a non-HTTPS
URI, is marked patient-level, or has a changed address.

Each record contains:

| Field | Requirement |
| --- | --- |
| `record_id` | unique aggregate identity |
| `operation` | one of the four C13-C16 operation IDs |
| `role` | `positive` or `control` |
| `expected_state` | `accepted`, `published`, or `review` |
| `context_key` | exactly the catalog context |
| `source_ids` | non-empty subset of declared source IDs |
| `expected_issue_codes` | explicit control issue vocabulary |
| `payload` | operation-shaped aggregate object |

The record address is computed from the record body without the address field.
The catalog address is computed from the full typed source and record
projection. Both are deterministic under canonical JSON serialization.

## Operation C13: preanalytic quality

`BiospecimenPreanalyticQualityAssessor` evaluates these default metrics:

| Metric | Rule in the checked-in fixture |
| --- | --- |
| `ischemia_minutes` | maximum 60 minutes |
| `storage_temperature_c` | minimum -90 C and maximum -60 C |
| `rna_integrity` | minimum 0.6 |

The adapter returns each observed numeric metric, failed metric names, a
bounded score, the source ID, and structured issues. Missing values produce a
`missing_quality_metric` issue and do not become an implicit pass. A value
outside a declared range produces `preanalytic_threshold_failed`.

The positive record has fifteen minutes of ischemia, -80 C storage, and an RNA
integrity value of 0.92. The controls include a ninety-minute ischemia value
and a record with no RNA-integrity metric. Both remain review. No score is
interpreted as a diagnostic or assay-acceptance claim.

## Operation C14: assay lineage

`AssayLineageProtocolTracker` retains a typed node with:

- node ID;
- aggregate specimen ID;
- protocol ID;
- optional parent node ID;
- assay label;
- operator label;
- declared start time; and
- structured issue state.

The positive record is a root node. One control points to a missing parent and
must retain `missing_parent_node`. The second control repeats a node ID and
must retain `duplicate_lineage_node`. A missing parent changes the affected
node to review; it does not cause the row to disappear. A duplicate does not
silently overwrite the first node.

The resulting graph is a declared processing lineage. It is not a custody
attestation, a specimen-authentication mechanism, or a claim of biological
ancestry. Temporal ordering and operator labels remain declared fields.

## Operation C15: identity adjudication

`IdentityConflictAdjudicator` counts observed aggregate identity labels and
computes modal agreement. A positive record has three concordant observations
and reaches the 0.8 default threshold. One control has a two-way tie and
retains `identity_tie`. The other has two observations of one label and one
of a different label and retains `identity_conflict`.

The operation can report a concordant mode, but the release gate does not
interpret that mode as authenticated specimen identity. The fixture uses
cohort-shaped labels rather than direct identifiers. A tie, conflicting mode,
empty observation set, or sub-threshold agreement remains review.

## Operation C16: context envelope

`SpecimenContextEnvelopePublisher` requires:

- a non-empty envelope ID;
- at least one aggregate specimen ID;
- a lineage receipt address;
- a quality receipt address; and
- an identity receipt address.

The release wrapper additionally checks that all addresses begin with
`sha256:` and that an optional payload context equals the record context. A
positive record publishes a deterministic publication address. One control
omits the identity address and retains `missing_identity_address`. The other
declares a different context and retains `envelope_context_mismatch`.

The envelope binds receipts; it does not upgrade a review receipt into an
accepted scientific result. Publication means that the declared envelope is
complete enough for this software boundary.

## Data audit checks

`audit_specimen_preanalytic_data` runs twenty-three checks in stable order:

| Check | Assertion |
| --- | --- |
| `fixture-version` | fixture version matches the locked release version |
| `context-shape` | context has six non-empty components |
| `context-exact` | context equals the checked-in exact key |
| `source-floor` | at least four receipts exist |
| `source-identity` | source IDs are unique |
| `source-public` | every receipt is non-patient-level |
| `source-addresses` | every source receipt has a SHA-256 address |
| `source-uris` | every URI uses HTTPS |
| `record-floor` | exactly twelve records exist |
| `record-identity` | record IDs are unique |
| `record-addresses` | every record address exists |
| `record-context` | every record context matches the catalog |
| `record-sources` | every record source is declared |
| `positive-floor` | four positive records exist |
| `control-floor` | eight controls exist |
| `role-partition` | roles partition the record set |
| `operation-coverage` | all four operation IDs are present |
| `operation-balance` | every operation has at least one record |
| `payload-boundary` | forbidden direct-identifier keys are absent |
| `payload-mappings` | every payload is an object |
| `fixture-address` | the catalog address recomputes |
| `source-coverage` | every record retains at least one source |
| `expected-state-roles` | positive and control state declarations are conservative |

The audit is a boundary check, not a source-truth validator. It proves that
the declared aggregate fixture respects its own contract.

## Fixture evaluation

`evaluate_specimen_preanalytic_fixture` routes all twelve records through the
four adapters. It emits one sanitized receipt per record. Each receipt has:

- record and operation identity;
- role and expected state;
- exact context;
- source IDs;
- observed state;
- sorted issue codes;
- a compact operation summary;
- ten record-level checks;
- an output content address; and
- a boolean pass value.

The aggregate evaluation adds five fixture checks, six aggregate receipt and
boundary checks, and ten checks per record. The checked-in result is therefore
131 checks. A positive result must match `accepted` or `published`; a control
must match `review`. The evaluator retains issue codes instead of flattening a
control into a generic failure.

The serialized evaluation contains `receipts` and `checks`, but not the raw
catalog `records` collection or a raw `payload` field. A recursive projection
boundary rejects the following keys:

```text
records, raw_records, payload, patient_id, subject_id,
medical_record_number, sample_patient_id, participant_id,
case_uuid, individual_id, person_id
```

The boundary is checked on the output projection. It is not a claim that a
field-name check can make arbitrary unreviewed text safe.

## Contracts

`default_specimen_preanalytic_contracts` returns four typed contracts. Each
contract declares required inputs, optional inputs, output fields, accepted
states, review states, and a safety boundary. The registry rejects duplicate
operations, missing operation coverage, overlapping positive/review states,
duplicate fields, and empty declarations.

The contract manifest is content-addressed and exposes the operation order.
It is used by the quality gate and the CLI command
`specimen-preanalytic-contracts`.

## Replay

The replay expectation locks:

- fixture identity;
- exact context key;
- a minimum of twelve receipts;
- a minimum of 120 checks;
- four positive records;
- eight control records; and
- all four operation IDs.

Replay starts a fresh evaluation and reports named expectation failures. It
does not regenerate an expected result from the replay report itself. A
changed output state, reduced check floor, changed context, or missing
operation prevents acceptance.

## Scenario matrix

The scenario report projects each receipt into one state-transition row. It
retains the record ID, operation, role, expected state, observed state, issue
codes, and a per-scenario address. The matrix requires exactly twelve rows and
requires all positive and control rows to preserve their declared transition.

The matrix is a release view. It does not discard controls simply because the
aggregate fixture passes.

## Lineage graph

`build_specimen_preanalytic_lineage` creates a typed source-to-result graph:

| Layer | Count | Relation |
| --- | ---: | --- |
| public source roots | 4 | source declares fixture |
| fixture root | 1 | fixture contains record |
| fixture records | 12 | record produces result |
| sanitized results | 12 | terminal result layer |

The graph has 29 nodes and 28 typed edges. The graph audit checks endpoint
resolution, node uniqueness, relation vocabulary, source roots, containment
count, production count, context consistency, address format, public flags,
deterministic graph addressing, and sanitized projection.

The graph is a provenance view for this software artifact. It does not make
any claim about biological ancestry or custody.

## Receipt-index reconciliation

The receipt index joins each fixture record address to its fresh evaluator
result address without copying the raw payload. Its sixteen checks are:

1. fixture identity;
2. exact context;
3. source-set equality;
4. entry count;
5. record identity equality;
6. record ID uniqueness;
7. operation coverage;
8. entry context consistency;
9. entry source consistency;
10. record-address equality;
11. result-address equality;
12. observed-state equality;
13. entry-address recomputation;
14. index-address recomputation;
15. result-address uniqueness; and
16. sanitized-index boundary.

The audit constructs a fresh evaluation rather than trusting the index as its
own expected result. Mutated result addresses, contexts, record IDs, entry
addresses, missing entries, and changed index addresses are all represented
by tests.

## Bundle

`SpecimenPreanalyticEvidenceBundleBuilder` creates a twelve-entry sanitized
bundle in JSON, CSV, or Markdown. Entries retain operation, role, expected and
observed state, issue codes, result address, and entry address. The bundle
also points to the evaluation and scenario addresses.

Accepted bundles require an accepted evaluation. A review bundle requires an
explicit `allow_review=True` opt-in and keeps the review state visible. The
builder verifies every entry address and the bundle address before a successful
CLI exit.

## Runtime

The runtime stages are fixed and ordered by operation:

1. `preanalytic_quality`;
2. `assay_lineage`;
3. `identity_adjudication`; and
4. `context_envelope`.

Each stage emits an input count, output count, state, issue-code set, and
address. Counts are conserved within each stage. The accepted fixture reaches
`published`; the review-only fixture reaches `review` and returns a non-zero
CLI exit code without publishing.

The runtime manifest contains stage receipts and addresses, not raw fixture
rows. A request must match the fixture context and must choose either
`accepted_only` or `allow_review` publish mode.

## Quality gate

`evaluate_specimen_preanalytic_quality_gate` composes the data audit,
evaluator, replay, scenario matrix, contracts, lineage graph, reconciliation,
bundle, and runtime. It exposes twenty-five top-level checks and the addresses
of each component report:

- data audit address is retained indirectly through its state check;
- evaluator address;
- replay address;
- scenario address;
- lineage address;
- reconciliation address;
- bundle address; and
- runtime address.

The gate requires 131 evaluator checks, 16 reconciliation checks, 12 scenario
rows, a 29-node/28-edge graph, a 12-entry accepted bundle, and four conserved
runtime stages. It is accepted only when every component is accepted and all
top-level checks pass.

## CLI

The complete command surface is:

```powershell
python -m glio_noncode audit-specimen-preanalytic-data examples/specimen-preanalytic-public-aggregate.json --output preanalytic-data.json
python -m glio_noncode evaluate-specimen-preanalytic-fixture examples/specimen-preanalytic-public-aggregate.json --output preanalytic-fixture.json
python -m glio_noncode replay-specimen-preanalytic-fixtures examples/specimen-preanalytic-public-aggregate.json --output preanalytic-replay.json
python -m glio_noncode specimen-preanalytic-quality-gate examples/specimen-preanalytic-public-aggregate.json --output preanalytic-quality.json
python -m glio_noncode evaluate-specimen-preanalytic-scenarios examples/specimen-preanalytic-public-aggregate.json --output preanalytic-scenarios.json
python -m glio_noncode specimen-preanalytic-contracts --output preanalytic-contracts.json
python -m glio_noncode build-specimen-preanalytic-bundle examples/specimen-preanalytic-public-aggregate.json --output preanalytic-bundle.json --format markdown
python -m glio_noncode specimen-preanalytic-lineage examples/specimen-preanalytic-public-aggregate.json --output preanalytic-lineage.json
python -m glio_noncode specimen-preanalytic-reconciliation examples/specimen-preanalytic-public-aggregate.json --output preanalytic-reconciliation.json
python -m glio_noncode run-specimen-preanalytic-pipeline examples/specimen-preanalytic-pipeline-accepted.json --output preanalytic-pipeline.json
```

Commands return zero only when their component report is accepted or the
contract manifest is emitted. Review evaluation, review bundles without
opt-in, and review runtime publication return non-zero while still writing a
sanitized report when the command supports an output path.

## CI

Continuous integration runs all ten commands above, the full unit-test
discovery command, compilation, and the other domain evidence surfaces. The
fixture command is run on Python 3.11, 3.12, and 3.13. A change to the
fixture, operation contracts, source set, projection boundary, or stage order
must pass all three interpreters before it can be released.

## Change rules

When adding a positive or control record:

1. keep the exact context key unless intentionally versioning the fixture;
2. add at least one source receipt covering the field vocabulary;
3. state the expected issue codes explicitly;
4. add an operation-level assertion and a control assertion;
5. update the record and catalog floors;
6. regenerate addresses through typed constructors;
7. update replay, scenario, and quality expectations; and
8. update the capability evidence note.

When adding a field:

1. add it to the operation contract;
2. decide whether it may appear in a sanitized result;
3. check it against the forbidden-key boundary;
4. add a round-trip test;
5. add a missing or invalid-field control; and
6. document whether it is a source vocabulary field or an internal summary.

When changing a state or issue code:

1. preserve existing meanings under existing IDs;
2. add a new code for a new failure meaning;
3. update positive and control fixtures together;
4. update the replay expectation; and
5. keep review states visible in bundles and runtime manifests.

## Verification checklist

Before release, verify:

- source receipts are unique, HTTPS, aggregate, and addressed;
- the exact six-part context is unchanged or versioned;
- there are twelve records, four positive, and eight controls;
- all four operations are covered;
- fixture evaluation reports 131 checks;
- each positive state is accepted or published;
- every control state is review;
- the contract registry covers four operations;
- replay passes its floors;
- the scenario matrix has twelve passing transitions;
- the graph has 29 nodes and 28 edges;
- reconciliation has 16 passing checks;
- the bundle has 12 entries and verifies;
- the runtime has four conserved stages;
- no raw payload collection appears in release projections; and
- the full local and CI suites pass.

The gate is intentionally evidence-oriented. Passing this document’s checks
means the software surfaces agree with the declared aggregate fixture. It does
not establish clinical utility, assay validation, identity authentication,
biological lineage, treatment response, or institutional release readiness.

## Operational invariants

The four operations share a common receipt vocabulary but do not share a
decision rule. The quality assessor may accept a bounded quality score, while
the lineage tracker may accept only when the declared parent is present. The
identity adjudicator may retain an unresolved tie, and the envelope publisher
may reject a record even when its local measurement is otherwise valid. This
separation is deliberate: a result must not inherit acceptance from a nearby
operation merely because both operations read the same fixture row.

Every operation receipt therefore carries its own operation name, record ID,
state, issue codes, content address, context key, and source IDs. The receipt
is a projection of the decision, not a copy of the input record. A projection
may include bounded counts and categorical diagnostics, but it must not copy
free-form payload text, subject identifiers, hidden tokens, or unreviewed
source fields. This makes the receipt suitable for comparison across the
evaluation, replay, lineage, reconciliation, bundle, and runtime views.

The following invariants are checked at the relevant boundary:

1. A source ID is unique within a fixture and every referenced source is
   declared as public, aggregate, and non-patient-level.
2. A record ID is unique across positive records and controls. A control ID may
   not collide with a positive record ID, even when the operation differs.
3. A record has one exact context key. Context components are ordered and are
   not silently normalized, guessed, or transported from another profile.
4. A positive record has one operation result. A missing result is a failure,
   and a duplicate result is a lineage error rather than a second opinion.
5. A control has an expected state and expected issue-code set. Controls are
   executable assertions, not comments attached to a fixture.
6. A result address is computed from its canonical typed fields. Reordering
   source IDs or checks must not change an address when the semantic content is
   unchanged; changing a decision field must change the address.
7. Each stage consumes exactly the prior stage’s accepted projection count and
   emits one stage receipt per input record. Count changes require an explicit
   issue and cannot be hidden in a summary field.
8. A published runtime state requires accepted data, accepted evaluation,
   accepted reconciliation, and an accepted bundle. A review state is retained
   when any required component is missing, contradictory, or out of scope.
9. A review result is not converted to accepted by lowering a threshold,
   removing a control, omitting a source, or suppressing an issue code.
10. All reports are deterministic for the same fixture, context, operation
    registry, and implementation version. Determinism is required for replay
    and for meaningful CI diffs.

## Failure and repair matrix

| Boundary | Observable failure | Required repair | Prohibited shortcut |
| --- | --- | --- | --- |
| Source catalog | Missing, duplicate, non-HTTPS, or patient-level source receipt | Correct the receipt or add an approved public aggregate source | Mark the source as trusted in a result row |
| Context | Wrong component count, ordering, or value | Correct the fixture context or version the fixture deliberately | Transport a nearby disease, age, tissue, or phase context |
| Quality | Missing metric or threshold failure | Supply a bounded metric with source coverage, or retain review | Convert missing into zero or pass |
| Lineage | Missing parent, duplicate node, or cycle | Repair node IDs and parent references, then replay | Collapse the graph to its final node |
| Identity | Tie, conflict, or missing receipt | Add independent aggregate evidence or keep review | Select the top candidate without a margin |
| Envelope | Context mismatch or absent identity address | Reconcile context and identity receipts | Publish a local measurement alone |
| Evaluation | Positive result absent or control expectation drifted | Add the missing result or update the declared control contract | Delete the failing control |
| Replay | Address, source, or floor drift | Regenerate typed artifacts and review the diff | Accept a changed address as equivalent |
| Reconciliation | Cross-view state, count, or source mismatch | Fix the first divergent view and rerun downstream views | Patch only the final report |
| Bundle | Entry missing, address mismatch, or unapproved review state | Rebuild the bundle with the correct opt-in | Export review entries as accepted |
| Runtime | Stage count not conserved or publication blocked | Repair the stage contract and rerun all stages | Bypass a stage with a hand-written receipt |

The first failing boundary is the repair starting point. Downstream reports
should be regenerated after the repair so that their addresses and source
sets describe the repaired input. A later report must not be edited to conceal
an earlier failure: the reconciliation layer exists specifically to expose
that kind of divergence.

## Review handoff contract

When a command returns review, its report remains useful. It must include the
fixture ID, fixture version, exact context key, operation, record or control
ID, state, issue codes, source IDs, and content address. It may also include
bounded observed values such as counts, booleans, and enumerated reasons. It
must not include the raw input record, hidden free-form fields, or any value
that would turn an aggregate fixture into a subject-level export.

A reviewer can use the report in this order:

1. Confirm the data-boundary checks and source receipt set.
2. Identify the first failed operation or stage and read its issue codes.
3. Compare the failed receipt with the corresponding control expectation.
4. Inspect the lineage and reconciliation views for count or address drift.
5. Decide whether the repair belongs in the fixture, a typed contract, or the
   operation implementation.
6. Rerun the focused command, then replay and the integrated quality gate.
7. Preserve the review artifact when the result remains unresolved.

The handoff is complete only when the receiving reviewer can reproduce the
same state from the checked-in fixture and the declared command. A screenshot,
manual spreadsheet, or unstated local override is not an evidence receipt.

## Test-vector expectations

The checked-in aggregate fixture intentionally contains paired positive and
control paths for each operation. The positive path demonstrates the smallest
accepted contract; the controls exercise failure meanings that are easy to
lose when implementations are simplified:

- quality controls distinguish a failed threshold from a missing metric;
- lineage controls distinguish a missing parent from a duplicate node;
- identity controls distinguish a tie from an explicit conflict and from a
  missing identity address; and
- envelope controls distinguish a context mismatch from a valid identity
  receipt.

Each control must fail for its declared reason and not merely because another
operation happened to fail first. The scenario matrix checks this isolation,
while the quality gate checks the integrated behavior. If a future operation
adds a new issue code, its positive and negative vectors must state whether
the code is mutually exclusive with existing codes or may be co-reported.

The minimum release evidence is consequently a set of mutually reinforcing
views rather than a single green command: public-data audit, operation
evaluation, replay, scenario transitions, contract manifest, lineage graph,
cross-view reconciliation, bundle verification, and runtime publication. A
release candidate that omits one of these views is incomplete even if the
remaining views report accepted.
