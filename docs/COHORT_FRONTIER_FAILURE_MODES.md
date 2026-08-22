# Domain 12 failure modes and response guide

This guide maps observable failures to the smallest safe response. The first
principle is preservation: keep the failing fixture, output, issue code, and
content address available until the cause is understood.

## Failure classes

Failures belong to one of five classes:

1. fixture boundary failure;
2. operation contract failure;
3. computation or mapping failure;
4. release assembly failure;
5. reproducibility or export failure.

The class determines which surface to inspect first. A release failure should
not be diagnosed by editing the fixture before checking the gate output.

## Fixture boundary failures

### Missing source receipts

**Signal:** data audit reports a missing source or the loader raises a source
section error.

**Likely cause:** a hand-authored fixture omitted the source section or used an
empty source ID.

**Response:** restore the source receipt, reference it from the affected record,
and rerun the data audit. Do not use a placeholder URI.

### Non-HTTPS source URI

**Signal:** source audit rejects a URI.

**Likely cause:** an internal path, an unencrypted URL, or a copied citation
without a resolvable scheme.

**Response:** use a public HTTPS receipt or mark the record unavailable. The
source note must describe the aggregate boundary.

### Duplicate record ID

**Signal:** fixture loading or audit rejects duplicate IDs.

**Likely cause:** a copied positive row was not assigned a new ID.

**Response:** choose a stable operation-scoped ID, update expected values, and
rerun all reconciliation checks.

### Context drift

**Signal:** boundary or record context checks fail.

**Likely cause:** a context string was edited, normalized differently, or copied
from a related but non-identical cohort.

**Response:** compare the fixture context, every record context, and the schema
context requirement. If the context change is intentional, create a new fixture
version.

### Missing evidence boundary

**Signal:** quality gate fails its boundary check.

**Likely cause:** the public aggregate token was omitted or replaced.

**Response:** restore the exact boundary token and check every export. Do not
release a manifest that relies on a reader remembering the boundary separately.

## Subgroup fairness failures

### High gap unexpectedly accepted

**Signal:** `C13-CTRL-001` has no issue or is marked supported.

**Likely cause:** the wrapper did not map the stratifier's review group, or a
threshold was changed without updating the control.

**Response:** inspect the stratifier report, maximum gap, threshold, and wrapper
mapping. Add a regression assertion for the affected group.

### Missing group treated as a valid stratum

**Signal:** `C13-CTRL-003` produces a rate for an empty or missing group.

**Likely cause:** input coercion replaced a missing field with a default label.

**Response:** preserve the invalid payload and reject it with
`invalid_fairness_input`.

### Small stratum disappears

**Signal:** a control output has fewer strata than its input groups.

**Likely cause:** an aggregation filter removed a small group.

**Response:** retain every declared group and make the denominator visible. A
small group may be review-worthy, but it must not be invisible.

## Transportability failures

### Feature gap becomes supported

**Signal:** `C14-CTRL-001` appears in `transportable_ids`.

**Likely cause:** source features were treated as a complete target set.

**Response:** calculate target-minus-source features explicitly and emit
`target_feature_gap`.

### Shift is hidden by overlap

**Signal:** a high-shift analysis has no review ID.

**Likely cause:** overlap and shift were collapsed into one score.

**Response:** retain both signals and apply the declared maximum shift threshold
independently.

### Empty population interpreted as transportable

**Signal:** an empty analysis list produces a supported report.

**Likely cause:** the loop returned an empty successful result without a boundary
issue.

**Response:** emit `empty_transportability_input` and keep the record invalid.

## Federated summary failures

### Privacy floor omitted

**Signal:** a site count below five is supported.

**Likely cause:** the floor was applied only to total count, not to each summary
group.

**Response:** evaluate the declared floor at the feature summary and retain the
affected feature in `review_ids`.

### Raw site values leak into export

**Signal:** a public JSON or CSV export contains unneeded site rows.

**Likely cause:** an internal input object was serialized rather than the
aggregate report.

**Response:** narrow the export to aggregate summaries, inspect the output, and
add a fixture assertion that raw rows are absent.

### Malformed mean accepted

**Signal:** a non-numeric mean reaches a supported summary.

**Likely cause:** string conversion occurred before numeric validation.

**Response:** validate numeric values before aggregation and emit
`invalid_federated_input`.

## Discovery failures

### Context mismatch publishes

**Signal:** `C16-CTRL-001` is published.

**Likely cause:** context was compared after publication or not compared at all.

**Response:** enforce exact context before building the publication address.

### Empty analysis set publishes

**Signal:** a feature-only bundle reaches published state.

**Likely cause:** analysis IDs were treated as optional metadata.

**Response:** require a non-empty analysis set and retain
`invalid_cohort_discovery_input`.

### Empty input creates a release address

**Signal:** an empty discovery payload has a publication address.

**Likely cause:** address calculation ran before input validation.

**Response:** validate required input first and emit
`empty_cohort_discovery_input`.

## Evaluation failures

### Check count changes unexpectedly

**Signal:** evaluation has a check count other than 120.

**Likely cause:** a record-level assertion was removed, a global assertion was
duplicated, or a fixture record was added without a corresponding check.

**Response:** inspect the evaluator construction. The default design has seven
checks per record and eight global checks: 112 plus 8 equals 120.

### Expected and observed states diverge

**Signal:** reconciliation lists one or more record IDs.

**Likely cause:** threshold, issue mapping, or output state changed.

**Response:** inspect the execution map and the record expectation side by side.
Do not update the fixture until the changed behavior is intentional and
versioned.

### Unexpected issue code

**Signal:** quality gate fails issue vocabulary.

**Likely cause:** a wrapper invented a string instead of using a contract code.

**Response:** either map the underlying signal to a declared issue or add a
versioned contract change with tests and documentation.

## Lineage failures

### Missing terminal

**Signal:** terminal address count is below 16.

**Likely cause:** an invalid or control execution was not connected to lineage.

**Response:** connect every fixture record, not only accepted records.

### Cyclic graph

**Signal:** lineage reports `acyclic` false.

**Likely cause:** an output address was reused as an input node or an edge was
reversed.

**Response:** inspect the source and fixture edge constructors and keep output
nodes downstream of inputs.

### Address instability

**Signal:** replay reports drift in execution or lineage addresses.

**Likely cause:** unordered input iteration, a clock value in the hash body, or
presentation fields mixed into canonical content.

**Response:** sort only where contract semantics allow, remove run-specific
values from stable bodies, and compare canonical JSON.

## Quality and release failures

### Gate is blocked by reconciliation

**Signal:** quality gate has a failed `reconciliation` row.

**Response:** stop release assembly and inspect the first mismatched record. The
gate is designed to block before distribution.

### Bundle is not publishable

**Signal:** release bundle has `publishable` false.

**Likely cause:** a positive policy decision is not publishable or the policy
decision set is incomplete.

**Response:** inspect all four decisions and the evaluation. Controls should not
be removed to make the bundle publishable.

### Release state is review

**Signal:** release manifest state is `review`.

**Likely cause:** bundle, quality gate, replay, or bundle-publishable check did
not pass.

**Response:** retain the review manifest and fix the failing upstream surface.
Never relabel the state in an export.

## Export failures

### CSV row count changes

**Signal:** review CSV has a line count other than 17 for the default fixture.

**Likely cause:** controls were filtered, a row contained an unescaped newline,
or the header changed.

**Response:** inspect the view rows and CSV writer. The fixed column order is
part of the review contract.

### JSON lacks a trailing newline

**Signal:** file comparison or CI formatting check fails.

**Likely cause:** a caller used a raw serializer instead of the export helper.

**Response:** use `export_cohort_frontier_json` for indented JSON output.

## Escalation order

When multiple failures occur, use this order:

1. fixture loader;
2. data audit;
3. operation execution;
4. evaluation;
5. reconciliation;
6. lineage;
7. quality gate;
8. runtime;
9. replay;
10. release;
11. export.

An upstream failure can explain several downstream failures. Fix the earliest
accurate boundary and rerun before changing later surfaces.

## Failure record

For every investigated failure retain:

- command;
- input path or default-fixture marker;
- stdout and stderr;
- fixture address;
- failed check IDs;
- observed value;
- required value;
- code change or fixture version;
- rerun command;
- final receipt.

This record keeps a failed path auditable and prevents a green rerun from
erasing the original symptom.
