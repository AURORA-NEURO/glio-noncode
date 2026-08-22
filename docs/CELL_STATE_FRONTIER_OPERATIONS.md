# Cell-State Frontier Operations Manual

This manual defines the operating contract for the Domain 08 cell-state frontier
evidence surface. It is written for maintainers who need to inspect a run,
reproduce a receipt, diagnose a failed check, or prepare a release bundle.

The surface accepts public aggregate observations only. It keeps the boundary
explicit at every stage: source selection, payload parsing, adapter execution,
state interpretation, quality review, release construction, and export.

## 1. Operating objective

The objective is to provide a reproducible evidence path for four cell-state
operations:

1. abundance intervals with uncertainty;
2. single-cell reference mapping;
3. out-of-domain detection;
4. context publication.

Each operation has one positive fixture record and three control records. The
positive record demonstrates the supported path. The controls exercise partial
coverage, missing context, malformed input, boundary mismatch, or a similar
failure mode. A run is useful only when both sides of that distinction remain
visible.

The operating surface therefore reports more than one pass flag. It reports:

- the source receipt set;
- the exact context key;
- the adapter state for each record;
- issue codes observed during evaluation;
- content addresses for intermediate artifacts;
- replay and reconciliation results;
- policy and schema checks;
- release and export summaries.

## 2. Boundary and vocabulary

The boundary for the default fixture is
`public_aggregate_non_patient`. This means that a payload is suitable for the
surface only when it describes a public aggregate or reference observation and
does not require an individual record to interpret the result.

The context key is:

`GRCh38|glioma|adult|stem_like|tumor|unknown`

The six fields are ordered and stable:

| Position | Field | Meaning |
| --- | --- | --- |
| 1 | genome | reference assembly used by the observation |
| 2 | disease | disease or model context |
| 3 | cohort | broad cohort grouping |
| 4 | state | cell-state label |
| 5 | compartment | tissue or sample compartment |
| 6 | sex | declared sex context or `unknown` |

The surface does not silently infer a missing field. A missing field produces an
issue code or a control state, depending on the operation contract.

## 3. Module map

The implementation is split into modules with narrow responsibilities.

| Module | Responsibility | Primary output |
| --- | --- | --- |
| `cell_state_frontier_public_data` | immutable fixture and source receipts | fixture |
| `cell_state_frontier_contracts` | operation contracts and field vocabulary | contract registry |
| `cell_state_frontier_fixture_eval` | adapter execution and checks | evaluation report |
| `cell_state_frontier_replay` | deterministic second evaluation | replay report |
| `cell_state_frontier_scenario_matrix` | expected state and issue floors | scenario report |
| `cell_state_frontier_policy` | scope, claim, and disclosure rules | policy report |
| `cell_state_frontier_lineage` | source-to-receipt edge construction | lineage report |
| `cell_state_frontier_reconciliation` | expected versus observed state comparison | reconciliation report |
| `cell_state_frontier_bundle` | composition of the evidence artifacts | bundle |
| `cell_state_frontier_schema` | serialized shape validation | schema report |
| `cell_state_frontier_quality_gate` | release acceptance decision | quality report |
| `cell_state_frontier_runtime` | one named pipeline run | runtime result |
| `cell_state_frontier_release` | release manifest construction | release manifest |
| `cell_state_frontier_observability` | stage trace and run comparison | trace/comparison |
| `cell_state_frontier_views` | review-oriented rows and source rows | view |
| `cell_state_frontier_exports` | JSON, CSV, and Markdown exports | export text |

The modules communicate through frozen dataclasses and tuples. A caller should
not mutate a report after it is returned. If a changed report is needed for a
test, construct a replacement value and preserve the original report.

## 4. Standard run sequence

The canonical runtime sequence has nine stages. The stage order is part of the
trace contract.

### 4.1 Data audit

The data audit checks fixture identity, source receipts, source identifiers,
context keys, payload presence, and boundary declaration. It does not execute
an adapter. Its role is to establish that the input is eligible for evaluation.

Expected result for the default fixture:

- 16 records;
- 5 source receipts;
- 4 positive records;
- 12 control records;
- one context key;
- one declared boundary;
- accepted status.

If the data audit fails, later stages may still be inspected for diagnostics,
but the release gate must remain closed.

### 4.2 Evaluation

The evaluator loads the operation contract for each record, invokes the existing
frontier adapter, and converts the result into a stable receipt. Each receipt
contains the record identifier, operation, context, adapter state, issue codes,
source identifiers, and a content address.

The evaluator keeps failures local. A malformed control record must not prevent
the other fifteen records from producing receipts. A record-level exception is
converted into an issue code and a non-success state.

### 4.3 Replay

Replay executes the same interpretation path from the same fixture and compares
the state sequence and receipt-address sequence. The default run must be
deterministic. A state change and an address change are separate checks because
they represent different failure classes.

Replay is not a substitute for source validation. It proves that the local
pipeline is stable for the selected fixture; it does not prove that a remote
source has not changed.

### 4.4 Scenarios

The scenario matrix maps each record to its expected state and required issue
floor. Positive records require `supported`. Controls require either `partial`
or `out_of_domain`. A control that is accidentally accepted is a scenario
failure even when its output is well formed.

The scenario matrix is intentionally explicit so that a future fixture change
must update an expectation rather than silently weaken a test.

### 4.5 Policy

Policy evaluation checks boundary, source class, disclosure, and claim scope.
The policy layer does not determine biological truth. It determines whether the
shape and scope of a result are suitable for the declared public aggregate
surface.

Policy failures are release blockers. A record may have a valid adapter output
and still fail the policy layer if the output makes a claim outside its declared
scope.

### 4.6 Schema

Schema validation checks one schema per operation. The checks cover required
payload fields, result fields, issue vocabulary, state vocabulary, and address
shape. A schema result is attached to the bundle so that exports carry the same
shape decision as the run.

The schema layer is intentionally independent of the fixture evaluator. This
allows contract review to detect a field omission before a new source payload is
introduced.

### 4.7 Lineage

Lineage creates one edge per receipt. Each edge records its source identifiers,
operation, output state, output address, and transformation label. The report
also carries the complete source identifier set from the fixture.

Lineage closure requires:

- every receipt has at least one source;
- every receipt has a matching edge;
- every edge points to a known record;
- every edge operation matches its receipt;
- the fixture source set equals the lineage source set;
- every edge has a content address.

### 4.8 Reconciliation

Reconciliation compares the scenario expectation with the observed receipt for
each record. It reports expected state, observed state, expected issue floor,
observed issue codes, and a pass flag. It also reports three global checks for
record closure, source closure, and operation closure.

The reconciliation report is the clearest place to diagnose a state mismatch.
The quality gate consumes it but does not replace it.

### 4.9 Bundle

The bundle composes all prior reports and adds a stable record identifier list.
The bundle address is computed from its content. A release may refer to the
bundle address without copying every nested detail into an external index.

## 5. Operation runbooks

### 5.1 Abundance interval

The abundance operation expects a sequence of public aggregate rows with a
count, denominator, and uncertainty field. The positive fixture demonstrates a
valid interval. Controls cover missing counts, invalid denominators, and absent
context.

Review the following fields first:

- `input_text` contains a serialized row sequence;
- `context_key` matches the declared context;
- `source_ids` is non-empty;
- the adapter state is `supported` only for the positive;
- uncertainty-related issue codes are present when a control is partial.

An interval result should be interpreted as an aggregate observation. It is not
an individual-level estimate and should not be exported with an individual
claim.

### 5.2 Reference mapping

The mapping operation expects marker or feature rows that can be compared with a
public reference profile. The positive fixture has sufficient overlap. Controls
cover insufficient overlap, missing reference context, and malformed rows.

Review the following fields first:

- reference context is declared;
- feature rows are parseable;
- overlap or match details are represented in the result;
- controls are not promoted to `supported`;
- the receipt retains all source identifiers.

Mapping results should be described as reference compatibility, not as a claim
that every observed cell has a single definitive identity.

### 5.3 Out-of-domain detection

The out-of-domain operation compares the requested context and observed fields
with the declared domain. The positive fixture is within the supported domain.
Controls cover missing context, incompatible labels, and invalid field values.

Review the following fields first:

- the requested context is present;
- the observed domain fields are normalized;
- incompatible values produce `out_of_domain` or `partial`;
- issue codes explain the boundary decision;
- no unsupported claim is emitted from a control.

An out-of-domain result is a boundary decision for this surface. It is not a
general statement about the source or the underlying biology.

### 5.4 Context publication

The publication operation checks whether a result can be represented under the
declared context and disclosure rules. The positive fixture has a complete
context envelope. Controls cover omitted fields, incompatible boundary values,
and invalid summaries.

Review the following fields first:

- all six context positions are available;
- the boundary is explicit;
- the summary is aggregate and non-individual;
- missing envelope fields remain visible;
- the publication state matches the contract.

Publication is a packaging decision. It should not be read as independent
validation of a source claim.

## 6. Quality-gate interpretation

The default quality gate has twelve checks. The check identifiers are stable and
should be used in dashboards, pull-request notes, and release records.

| Check | Meaning | Typical action on failure |
| --- | --- | --- |
| `data-audit` | fixture boundary is eligible | inspect source and payload metadata |
| `evaluation` | receipts cover every record | inspect adapter output and issue codes |
| `replay` | repeated run is stable | compare state and receipt addresses |
| `scenarios` | expected state floors hold | inspect the affected fixture row |
| `policy` | scope rules hold | narrow boundary or claim |
| `schema` | four operation schemas pass | update contract or serializer |
| `lineage` | source closure holds | restore source-to-receipt edge |
| `reconciliation` | expected and observed states agree | inspect record-level delta |
| `record-closure` | all record identifiers are present | inspect fixture/evaluation join |
| `source-closure` | all source identifiers are present | inspect receipt source set |
| `operation-closure` | all four operations are covered | inspect contract registry |
| `bundle` | content-addressed bundle is valid | inspect nested artifact addresses |

The quality report is accepted only when every check passes. A run with one
failed check is retained for diagnosis but must not be included in a release
index.

## 7. Failure diagnosis matrix

Use the first failing stage as the starting point. Later failures may be
consequences of the same root cause.

| Symptom | First inspection | Likely cause |
| --- | --- | --- |
| no records in a view | data audit | fixture selection or parse boundary |
| one receipt missing | evaluation | record exception or identifier mismatch |
| state replay failure | replay | adapter behavior changed or fixture drift |
| address replay failure | replay | serialization order or content changed |
| positive state mismatch | scenarios | expected state or adapter contract changed |
| control accepted | scenarios | control payload is too permissive |
| policy failure | policy | boundary or disclosure rule mismatch |
| schema failure | schema | contract fields and serializer diverged |
| missing lineage edge | lineage | receipt was created outside the edge builder |
| source closure failure | lineage/reconciliation | source receipt omitted from a report |
| operation closure failure | reconciliation | contract or fixture omitted an operation |
| release rejected | quality gate | one or more upstream checks failed |
| CSV row count mismatch | exports | view and export selection diverged |
| Markdown table mismatch | exports | display formatter lost a review row |

## 8. Determinism checklist

Before reviewing a change, run the following checks:

1. load the default fixture twice;
2. compare fixture addresses;
3. evaluate both fixture objects;
4. compare receipt state sequences;
5. compare receipt address sequences;
6. build both bundles;
7. compare bundle addresses;
8. run the runtime comparison helper;
9. confirm that the state-change list is empty;
10. confirm that the quality check set is unchanged.

Do not use wall-clock values, random identifiers, unordered serialization, or
environment-specific paths in content-addressed payloads. If a diagnostic needs
time, keep that value outside the addressed artifact.

## 9. Source receipt review

The source list contains five public references. Each source receipt should be
reviewed for identifier, title, locator, scope, and content address.

The review process is:

1. confirm the locator resolves to the intended public data landing page;
2. confirm the source scope matches aggregate or reference use;
3. confirm the fixture references the source by stable identifier;
4. confirm every receipt source identifier appears in the source list;
5. confirm the lineage report carries the same source set;
6. confirm exports preserve source identifiers without rewriting them;
7. record a fixture update when the source purpose changes.

The default implementation stores source receipts as fixture data. It does not
silently fetch remote content during the normal test path. A future ingestion
layer may add refreshed material, but it must preserve the same receipt and
lineage contracts.

## 10. Review queue procedure

The review view contains twelve control rows and five source rows. Positive rows
are available for inspection but do not enter the default review queue.

For each review row:

- confirm the priority is derived from state and issue severity;
- inspect the record identifier;
- inspect the operation and context key;
- inspect the observed state;
- inspect issue codes;
- inspect source identifiers;
- inspect the content address;
- record the disposition outside the immutable report.

The view is a presentation projection. It must not become a second evaluation
engine. If a new review rule is needed, add it to policy or quality checks first,
then expose its result in the view.

## 11. Export procedure

The export module supports four formats: JSON, CSV review rows, CSV sources,
and Markdown review text. The exported artifacts should be generated from the
same view and bundle used by the quality gate.

Before publishing an export:

1. run the quality gate;
2. reject the export when the gate is not accepted;
3. create the release manifest;
4. verify the manifest points to the bundle address;
5. export the review rows;
6. export the source rows;
7. confirm the CSV row counts;
8. confirm the Markdown record identifiers;
9. preserve the JSON manifest beside the human-readable files.

The CSV format is intended for review queues and simple downstream loading. It
is not the canonical machine contract; the JSON structures and content
addresses are canonical.

## 12. Release procedure

A release is a named view over an accepted bundle. The release manifest should
contain:

- release identifier;
- fixture identifier;
- run identifier;
- bundle address;
- quality status;
- record count;
- positive count;
- control count;
- operation list;
- source list;
- content address.

The release builder should be called only after the quality gate. The builder
must reject an unaccepted quality report rather than creating a partially valid
manifest.

Release review sequence:

1. inspect the run identifier;
2. inspect quality checks;
3. inspect bundle address;
4. inspect record and source counts;
5. inspect operation closure;
6. inspect source closure;
7. inspect export row counts;
8. retain the manifest with the build record.

## 13. CLI command groups

The command line surface exposes the same artifacts available through Python.
Each command accepts the default fixture unless a specific fixture path is
provided by a future extension.

| Group | Purpose |
| --- | --- |
| `cell-state-frontier-audit` | inspect the input boundary |
| `cell-state-frontier-evaluate` | produce adapter receipts |
| `cell-state-frontier-replay` | verify repeatability |
| `cell-state-frontier-quality` | run the twelve-check gate |
| `cell-state-frontier-scenarios` | inspect expected state floors |
| `cell-state-frontier-policy` | inspect scope decisions |
| `cell-state-frontier-contracts` | inspect operation contracts |
| `cell-state-frontier-schema` | inspect schema checks |
| `cell-state-frontier-metrics` | inspect aggregate metrics |
| `cell-state-frontier-bundle` | inspect composed evidence |
| `cell-state-frontier-lineage` | inspect source edges |
| `cell-state-frontier-reconciliation` | inspect state deltas |
| `cell-state-frontier-pipeline` | run the full sequence |
| `cell-state-frontier-release` | produce a release manifest |
| `cell-state-frontier-view` | produce review rows |
| `cell-state-frontier-trace` | produce stage events |
| `cell-state-frontier-receipts` | export receipt records |
| `cell-state-frontier-review` | export review data |
| `cell-state-frontier-review-markdown` | export review text |
| `cell-state-frontier-metrics-csv` | export metric rows |

For a build check, run the pipeline, quality, replay, release, review, and
metrics commands. For a diagnosis, begin with audit, evaluate, reconciliation,
lineage, and trace.

## 14. Test layers

The test suite is deliberately layered.

### 14.1 Evidence tests

Evidence tests confirm the default fixture, all four operations, all five source
receipts, positive/control counts, quality acceptance, and export counts.

### 14.2 CLI tests

CLI tests invoke the command groups and verify valid JSON or tabular output. A
CLI command is considered covered only when its output is parsed and checked,
not merely when the process exits successfully.

### 14.3 Depth tests

Depth tests exercise issue floors, malformed rows, boundary mismatch, schema
drift, policy drift, replay drift, lineage closure, and release rejection.

### 14.4 Contract matrix

The contract matrix tests each operation registry entry, required fields, state
vocabulary, source closure, reconciliation, runtime comparison, and every export
projection. It is the broadest local test layer for Domain 08.

When adding a new operation, extend all four layers. A new adapter without a
fixture control, contract row, schema row, policy row, and export assertion is
not a complete module addition.

## 15. Change protocol

A Domain 08 change should follow this sequence:

1. identify the affected contract;
2. update the smallest module that owns the rule;
3. add or update a positive fixture assertion;
4. add or update a control fixture assertion;
5. update schema and policy checks if the boundary changed;
6. update lineage or reconciliation checks if identifiers changed;
7. run focused tests;
8. run focused lint;
9. run CLI commands for affected exports;
10. run the full suite;
11. scan added lines for prohibited repository metadata markers;
12. inspect the staged diff and line count;
13. commit a coherent build on the main integration line;
14. push both tracked refs;
15. inspect every relevant Actions job.

Keep commits cohesive. A contract change, its fixture controls, its schema
change, and its tests belong together when they form one reviewable build.

## 16. Safe extension points

The following extensions are compatible with the current surface when they
preserve the existing contracts:

- additional public source receipts;
- additional control records per operation;
- a new aggregate operation with its own contract;
- richer issue details in receipt payloads;
- a new view projection derived from the same bundle;
- additional export formats derived from the canonical JSON;
- refreshed fixture versions with explicit version identifiers;
- a remote ingestion layer that emits the same immutable source receipts.

The following changes require a contract review before implementation:

- changing the meaning of `supported`;
- removing a control state;
- changing context key order;
- omitting source identifiers from receipts;
- accepting individual-level payloads;
- changing content-address calculation;
- making quality checks advisory;
- moving policy decisions into presentation code.

## 17. Acceptance checklist

Use this checklist before marking a Domain 08 build ready for review:

- [ ] all four operation contracts are present;
- [ ] the fixture has four positive records;
- [ ] the fixture has twelve controls;
- [ ] five source receipts are present;
- [ ] all records have the exact context key;
- [ ] all records have a declared boundary;
- [ ] all receipts have an operation;
- [ ] all receipts have an adapter state;
- [ ] all receipts have source identifiers;
- [ ] all receipts have content addresses;
- [ ] replay passes;
- [ ] scenario checks pass;
- [ ] policy checks pass;
- [ ] schema checks pass;
- [ ] lineage closes;
- [ ] reconciliation closes;
- [ ] the bundle is accepted;
- [ ] the quality gate has twelve passing checks;
- [ ] the release manifest is accepted;
- [ ] review exports contain twelve control rows;
- [ ] source exports contain five rows;
- [ ] metrics cover four operations;
- [ ] the CLI command group has focused coverage;
- [ ] the full test suite passes;
- [ ] the staged diff has no prohibited repository metadata markers;
- [ ] the commit is on the main integration line;
- [ ] both remote refs are pushed;
- [ ] the corresponding Actions jobs pass.

## 18. Quick diagnostic examples

### 18.1 A control becomes supported

Start with reconciliation and locate the record identifier. Then inspect the
receipt issue codes, the contract control states, and the scenario expectation.
If the payload is intentionally stronger, update the fixture version and the
contract review. If it is not intentionally stronger, tighten the adapter input
validation or the control payload.

### 18.2 A receipt address changes

Compare the old and new receipt dictionaries. Check field ordering, omitted
values, normalized strings, and source identifier order. If the semantic result
did not change, the change is still a replay-visible contract change and needs a
versioned fixture decision.

### 18.3 A source closure check fails

Compare the source list, fixture record source identifiers, receipt source
identifiers, lineage source identifiers, and reconciliation source set. The
missing value is usually introduced when a new record is added without a source
receipt or when a source identifier is normalized in only one module.

### 18.4 A release is rejected

Inspect the quality report before inspecting the manifest. The release builder
should reject the manifest because an upstream check failed. Fix the first
failed quality check, rerun the complete pipeline, and construct a new manifest.

## 19. Ownership of invariants

The fixture module owns record and source identity. The contract module owns
operation vocabulary. The evaluator owns adapter receipts. Replay owns
determinism. Scenarios own expected state. Policy owns boundary interpretation.
Lineage owns source closure. Reconciliation owns observed versus expected state.
The bundle owns composition. Schema owns shape. The quality gate owns acceptance.
Runtime owns orchestration. Release owns publication shape. Observability owns
trace and comparison. Views and exports own projections only.

When a test fails, fix the invariant at its owner. Avoid adding a presentation
special case to hide a contract or evaluation failure.

## 20. Final operating principle

Every published cell-state result should answer five questions without hidden
context:

1. What operation was run?
2. What public aggregate sources support it?
3. What context and boundary were declared?
4. What state and issue codes were observed?
5. Which checks make the result eligible for release?

If any answer is missing, keep the result in the diagnostic surface and return
to the owning module before extending the release path.

## Appendix A. Field-level diagnostic guide

The following guide gives a fast inspection order for common fields. It is
intentionally repetitive: during a failed review, a precise field checklist is
more useful than a general description.

| Field | Inspect in | Expected property |
| --- | --- | --- |
| `fixture_id` | fixture, bundle, release | stable within a fixture version |
| `fixture_address` | audit, lineage, bundle | equals the fixture content address |
| `record_id` | fixture, receipt, view | unique and preserved end to end |
| `operation` | contract, receipt, schema | one of the four declared values |
| `role` | fixture, scenario, view | positive or control |
| `context_key` | fixture, receipt, policy | exact six-part context string |
| `boundary` | fixture, policy, release | public aggregate boundary |
| `source_ids` | fixture, receipt, lineage | non-empty and closed over sources |
| `input_text` | fixture, evaluator | parseable serialized rows |
| `adapter_state` | receipt, scenario | supported, partial, or out_of_domain |
| `issue_codes` | receipt, scenario, view | stable vocabulary for the operation |
| `content_address` | every artifact | sha256-prefixed content address |
| `expected_state` | scenario, reconciliation | declared fixture expectation |
| `observed_state` | receipt, reconciliation | adapter result state |
| `passed` | checks, view, release | derived from the owning invariant |
| `record_count` | bundle, release, metrics | sixteen for the default fixture |
| `positive_count` | metrics, release | four for the default fixture |
| `control_count` | metrics, release | twelve for the default fixture |
| `source_count` | metrics, release | five for the default fixture |
| `operation_count` | contracts, metrics | four for the default fixture |

When a field is absent, first determine whether the absence is intentional. A
control payload may intentionally omit a field to test the boundary. A report
artifact should not omit the same field if its schema requires it. The evaluator
and schema validator must agree about the distinction.

### Appendix A.1 State review order

Review state mismatches in this order:

1. compare record identifier;
2. compare operation;
3. compare expected state;
4. compare observed state;
5. compare issue codes;
6. compare source identifiers;
7. compare content address;
8. compare scenario check;
9. compare reconciliation item;
10. compare quality check.

This order moves from identity to interpretation and then to aggregation. It
prevents a bundle-level failure from obscuring a single-record cause.

### Appendix A.2 Source review order

Review source mismatches in this order:

1. compare source identifier spelling;
2. compare source locator;
3. compare source scope;
4. compare fixture source list;
5. compare record source identifiers;
6. compare receipt source identifiers;
7. compare lineage source identifiers;
8. compare source export rows;
9. compare release source list;
10. rerun source closure.

Do not repair a source mismatch in an export formatter. The source receipt and
lineage owners must be corrected first.

### Appendix A.3 Content-address review order

Review address mismatches in this order:

1. serialize the smallest changed artifact;
2. compare keys and values;
3. compare tuple ordering;
4. compare normalized text;
5. compare omitted versus explicit null values;
6. compare nested receipt order;
7. compare source identifier order;
8. compare the parent artifact address;
9. rerun replay;
10. rerun the quality gate.

Addresses are diagnostic evidence. They should not be manually edited to make a
report appear stable.

### Appendix A.4 Review handoff record

A concise review handoff should include:

- run identifier;
- fixture identifier;
- first failing stage;
- failed check identifiers;
- affected record identifiers;
- affected operation values;
- source identifiers;
- old and new content addresses when relevant;
- local test command;
- full-suite result;
- remote Actions result;
- disposition and next module.

This record keeps a later review grounded in observable artifacts rather than
memory of an earlier run.

### Appendix A.5 Minimal evidence packet

The smallest useful evidence packet contains the fixture address, run identifier,
quality report, bundle address, release manifest, review rows, source rows, and
the failed-check list when the run is rejected. Keep the packet together so a
review can move from the release decision back to the exact receipt without
reconstructing intermediate state. If a packet is copied between environments,
preserve the JSON representation and its content addresses. Human-readable
tables are helpful for inspection, but the addressed JSON remains the reference
for comparison, replay, and later reconciliation.

Packet review should confirm that the same run identifier appears in the trace,
release, and export headers. A missing match indicates that two runs were
combined during packaging. In that case, discard the mixed packet, rerun the
pipeline, and produce a fresh release from one accepted bundle.

The packet is complete when a reviewer can identify the input, the operation,
the source boundary, the observed state, the checks, and the release decision
without consulting an unrelated run.

If the packet cannot meet that standard, keep it as a diagnostic artifact and
return it to the first failing stage for correction.

The diagnostic artifact remains valuable because it preserves the failed check
and its address. Never replace a failed packet with a passing packet without
retaining the failed run identifier for review history.

This preserves traceability.
