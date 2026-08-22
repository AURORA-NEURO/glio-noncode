# Domain 13 planning failure modes

Preserve the failing fixture, output, issue code, and address before applying a
fix. The earliest accurate failure is usually the most useful one.

## Fixture failures

### Missing source or record sections

**Signal:** fixture loading raises the required source and record error.

**Cause:** a hand-authored JSON object omitted a section or supplied an empty
array.

**Response:** restore typed public source receipts and records. Do not substitute
an empty fixture for a planning run.

### Duplicate record IDs

**Signal:** catalog record count does not equal unique record count.

**Cause:** a copied positive or control row was not assigned a stable ID.

**Response:** assign an operation-scoped ID and rerun evaluation and lineage.

### Context drift

**Signal:** record or boundary context check fails.

**Cause:** a context segment was edited or copied from a related cohort.

**Response:** compare all context segments. If the change is intentional, create
a new fixture version.

### Unaddressed source

**Signal:** source receipt or record lacks a SHA-256-style address.

**Cause:** an object was constructed without hashing its semantic body.

**Response:** calculate the address after all semantic fields are present.

## C01 failures

### Gap disappears

**Signal:** C01 positive has no gaps despite missing evidence or high uncertainty.

**Cause:** the wrapper dropped `missing_evidence` or applied a threshold before
building the typed hypothesis.

**Response:** inspect hypothesis conversion and the analyzer input. Preserve both
the missing channel and uncertainty gap.

### Context mismatch remains partial

**Signal:** C01 context control is not invalid.

**Cause:** the wrapper compared record context but not hypothesis context.

**Response:** enforce exact equality before accepting the gap report and emit
`context_mismatch`.

### Missing hypothesis is coerced

**Signal:** C01 invalid-input control produces an empty report.

**Cause:** missing payload was replaced with a default object.

**Response:** reject the record with `invalid_evidence_gap_input`.

## C02 failures

### Model mismatch routes as ready

**Signal:** C02 model control is ready for review.

**Cause:** model support was inferred from assay identity rather than inventory.

**Response:** require exact model membership and retain
`model_system_not_available`.

### Missing controls are hidden

**Signal:** a route with one control satisfies a two-control constraint.

**Cause:** set difference was not applied to required controls.

**Response:** retain `missing_controls` and keep the route blocked.

### Missing readouts are hidden

**Signal:** barcode-only inventory satisfies barcode and RNA readouts.

**Cause:** readout validation checked any overlap rather than all required values.

**Response:** retain `missing_readouts` separately from control issues.

### Empty inventory is treated as negative evidence

**Signal:** empty inventory returns blocked with an assay conclusion.

**Cause:** no route was represented as an ordinary failure.

**Response:** use `abstained` and `assay_not_present_in_inventory`.

## C03 and C04 failures

### Context mismatch creates constructs

**Signal:** a mismatched target appears in the construct list.

**Cause:** context was checked after construct creation.

**Response:** gate target before construct generation and retain the target ID in
the blocker.

### Reference allele mismatch is ignored

**Signal:** a target sequence does not contain the declared reference allele but
the package is ready.

**Cause:** target conversion bypassed `ValidationTarget` validation.

**Response:** preserve the validation error and return invalid design input.

### Construct budget truncates a pair

**Signal:** one of the reference or alternate constructs is silently dropped.

**Cause:** budget was applied by slicing output.

**Response:** retain the pair and emit `max_constructs_exceeded`.

### Empty target list is ready

**Signal:** a package with no targets is ready for review.

**Cause:** planner state was based only on the absence of blockers.

**Response:** emit `no_validation_targets` and block the package.

### Insert bound is bypassed

**Signal:** an eight-base target passes a six-base maximum.

**Cause:** the wrong sequence field or bound was used.

**Response:** compare target length with both constraint bounds and emit
`insert_length`.

## Evaluation failures

### Check count changes

**Signal:** evaluation has a count other than 120.

**Cause:** a record check or global check was removed or duplicated.

**Response:** maintain seven checks per record and eight global checks unless the
fixture version explicitly changes.

### Issue tuple differs

**Signal:** reconciliation reports an issue mismatch.

**Cause:** wrapper mapping, blocker spelling, or sort order changed.

**Response:** inspect the raw planner output, then update the mapping only when
the contract change is intentional.

### Positive acceptance changes

**Signal:** a positive row is not accepted.

**Cause:** planner threshold, target conversion, or context changed.

**Response:** inspect state and issue output. Do not change expected state solely
to make the run pass.

## Lineage failures

### Only positive rows have lineage

**Signal:** terminal count is below sixteen.

**Cause:** blocked controls were filtered before graph construction.

**Response:** connect every fixture record to its execution.

### Edge count changes

**Signal:** default edge count is not 36.

**Cause:** source citations changed or fixture edges were omitted.

**Response:** inspect source IDs and confirm four positive rows have two sources
and twelve controls have one source.

### Address drift

**Signal:** replay reports changed evaluation address without a semantic change.

**Cause:** unordered fields, run values, or timing values entered a stable hash.

**Response:** isolate run-specific values and hash only semantic fields.

## Quality and release failures

### Gate blocks on audit

**Signal:** data-audit is false.

**Response:** fix fixture structure before reviewing downstream surfaces.

### Gate blocks on reconciliation

**Signal:** mismatched IDs are present.

**Response:** preserve the mismatch, inspect state and issue tuple, and rerun.

### Bundle is not publishable

**Signal:** one of four positive decisions is blocked.

**Response:** inspect its execution and policy rule. Controls should not be
removed to make the bundle publishable.

### Release is review

**Signal:** any one of the four release checks fails.

**Response:** retain the review manifest and fix the upstream surface.

## Export failures

### CSV loses controls

**Signal:** fewer than 17 lines or no control IDs.

**Cause:** view filtering occurred before CSV export.

**Response:** export all view rows and use the fixed column order.

### JSON is not deterministic

**Signal:** canonical output changes across replay.

**Cause:** unsorted keys, unstable sets, or timing fields entered canonical
serialization.

**Response:** use the repository serializer and compare stable report fields.

## Escalation order

1. loader;
2. data audit;
3. typed conversion;
4. operation execution;
5. evaluation;
6. reconciliation;
7. lineage;
8. quality gate;
9. runtime;
10. replay;
11. release;
12. export.

## Failure record

Retain command, input, stderr, fixture address, failed IDs, observed value,
required value, code or version change, rerun command, and final receipt. This
keeps the original failure inspectable after a successful rerun.
