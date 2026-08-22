# Evidence Lifecycle Frontier Failure Modes

## Reading this guide

Each failure mode has a visible issue code.

Each failure mode has an observed state.

Each failure mode has a control record.

Each failure mode remains in the evaluation output.

Each failure mode remains in the review view.

Each failure mode remains in the review queue.

The failure mode is not deleted after detection.

The failure mode is not converted to a generic error.

The failure mode is not treated as a clinical conclusion.

## General input failures

### Missing fixture sources

The loader requires a source list.

An absent source list is invalid.

An empty source list is invalid.

The loader raises a clear value error.

The CLI returns a nonzero result.

The output does not claim acceptance.

### Missing fixture records

The loader requires a record list.

An absent record list is invalid.

An empty record list is invalid.

The loader raises a clear value error.

The CLI returns a nonzero result.

The output does not claim acceptance.

### Missing fixture metadata

Fixture ID is required.

Fixture version is required.

Context key is required.

Evidence boundary is required.

Missing metadata does not use a hidden default.

Missing metadata blocks data audit.

### Invalid source URI

Source URI must use HTTPS.

An HTTP URI is rejected.

A blank URI is rejected.

A local URI is rejected.

The source record remains a failed input.

### Duplicate source ID

Source IDs must be unique.

Duplicate source identity breaks binding.

The data audit reports the failure.

The evaluator does not infer a source choice.

## C01 citation failures

### Invalid JSON

Invalid JSON is parsed into an issue.

The issue code is `invalid_json`.

The state is `abstained`.

The raw input hash is retained.

The row is not silently dropped.

The control remains non-accepted.

### Missing table header

An empty TSV or CSV has no header.

The issue code is `missing_header`.

The state is `abstained`.

The input hash is retained.

The control remains visible.

### Missing source URI

A citation requires a source URI.

Aliases are checked.

An empty URI fails the required-field check.

The issue code is `missing_required_field`.

The raw row is retained.

The citation is not accepted.

### Missing title

A citation requires a title.

An empty title fails the required-field check.

The issue code is `missing_required_field`.

The raw row is retained.

The citation is not accepted.

### Missing citation text

A citation requires citation text.

An empty text field fails the required-field check.

The issue code is `missing_required_field`.

The raw row is retained.

The citation is not accepted.

### Duplicate citation ID

Citation IDs must be unique in a batch.

A repeated ID is quarantined.

The issue code is `duplicate_citation_id`.

The first row remains accepted when valid.

The batch is partial.

### Unsupported citation format

The resolver accepts TSV.

The resolver accepts CSV.

The resolver accepts JSON.

An unsupported format raises a validation error.

The command returns nonzero.

The input is not reinterpreted silently.

### Non-object JSON row

JSON citation rows must be objects.

A scalar row is quarantined.

The raw value receives a hash.

The issue remains in the batch.

### Missing deterministic retrieval time

Fixture rows provide retrieval time.

Live ad hoc input may use a fallback time.

Replay fixtures must avoid fallback time.

A time-dependent fixture causes address drift.

The replay test detects the drift.

## C02 graph failures

### Duplicate claim ID

Claim IDs must be unique.

Duplicate claim IDs block graph construction.

The issue code is `duplicate_claim_id`.

The execution state is `invalid`.

The control remains visible.

### Duplicate citation ID

Citation IDs must be unique in a graph.

Duplicate citation IDs block graph construction.

The error remains attached to the execution.

The graph is not partially guessed.

### Claim context mismatch

Each claim must match graph context.

A mismatched claim raises a validation error.

The issue code is `graph_context_mismatch`.

The execution state is `invalid`.

The claim is not transported to another context.

### Missing parent claim

Parent claim IDs are checked.

An unknown parent marks the claim orphaned.

The graph state is `partial`.

The issue code is `orphan_claim`.

The claim remains in graph history.

### Missing supersession target

Supersession targets are checked.

An unknown target marks the claim orphaned.

The graph state is `partial`.

The issue code is `orphan_claim`.

The claim remains inspectable.

### Missing citation source

Claim source IDs are checked.

An unknown source marks the claim orphaned.

The graph state is `partial`.

The issue code is `orphan_claim`.

No source is inferred.

### Supersession cycle

The graph preserves supersession history.

A cycle is a review condition.

The cycle is not silently collapsed.

The active view must be inspected.

The control remains visible.

### Empty graph

An empty claim list abstains.

The state is `abstained`.

The graph has no active claim.

The graph has no false negative.

## C03 edge failures

### Missing edge

An unknown edge ID has no claim rows.

The edge state is `abstained`.

The issue code is `edge_absent`.

The output retains the edge ID.

The result is not a negative measurement.

### Missing edge source

An active claim may lack a citation.

The edge state is `partial`.

The missing source ID is listed.

The issue code is `missing_source`.

The result remains review-required.

### Edge context mismatch

An expected context may be supplied.

A mismatched expected context is out of domain.

The issue code is `edge_context_mismatch`.

The warning remains visible.

The edge is not reinterpreted locally.

### Contradictory edge

An edge may have positive and negative active claims.

The contradiction flag is true.

The state is contradictory.

No support average is produced.

The edge remains review-required.

### Orphan edge

An edge may include an orphan claim.

The orphan IDs remain visible.

The state is partial.

The edge is not treated as supported.

## C04 disagreement failures

### Contradictory observations

Positive and negative claims may coexist.

The state is contradictory.

The issue code is `contradiction_unresolved`.

Positive IDs remain separate.

Negative IDs remain separate.

Value groups remain separate.

Source IDs remain separate.

### Incomplete edge

An edge with no active claims is incomplete.

The state is `incomplete`.

The issue code is `incomplete_disagreement`.

The edge remains in the report.

The edge is not clear.

### Out-of-domain claim

An out-of-domain claim is not local evidence.

The state is `out_of_domain`.

The issue code is `disagreement_out_of_domain`.

The claim remains in the record.

The record remains non-accepted as a control.

### Clear observation

A single resolved observation is clear.

The state is `clear`.

Clear is not causal proof.

Clear is not a clinical conclusion.

Clear has no unresolved issue code.

## Evaluation failures

### State mismatch

Observed state must equal expected state.

A mismatch fails the state check.

The failed check ID includes the record ID.

The evaluation becomes non-accepted.

### Issue mismatch

Observed issue codes must equal expected issue codes.

Issue order is normalized.

A missing code fails evaluation.

An extra code fails evaluation.

The issue check remains inspectable.

### Role mismatch

Positive and control roles are distinct.

Positive expected acceptance is true.

Control expected acceptance is false.

A role mismatch fails evaluation.

### Operation mismatch

Execution operation must match record operation.

An operation mismatch fails evaluation.

No result is moved between operations.

### Address mismatch

Execution must have a SHA-256 content address.

Missing address fails evaluation.

Address format is checked for every record.

### Context mismatch

Record context must equal fixture context.

A context mismatch fails evaluation.

The mismatch is not hidden by output state.

### Empty output

Every execution retains an output object.

An empty output fails evaluation.

An error output is still non-empty.

## Replay failures

### Current timestamp drift

Current time changes citation content.

Current time changes graph content.

Current time changes execution addresses.

The replay comparison reports address drift.

Fixture data must use fixed timestamps.

### Unordered source input

Source order can affect serialized content.

Fixture source order is fixed.

Lineage uses explicit ordering.

Canonical export uses sorted keys.

Replay should remain stable.

### Unstable issue order

Issue sets are sorted before comparison.

Issue summaries are sorted.

The contract vocabulary is sorted.

Replay does not depend on set iteration order.

## Lineage failures

### Missing source edge

Every record source ID creates an edge.

A missing edge lowers traceability.

The edge count check detects the omission.

The quality gate blocks incomplete lineage.

### Missing fixture edge

Every record binds to fixture ID.

A missing fixture edge breaks aggregate traceability.

The terminal count check detects the omission.

### Duplicate item edge

Duplicate edges may hide source multiplicity.

Source edge ordinal is included in address material.

The edge count is explicit.

## Policy failures

### Missing positive path

Policy requires one positive per operation.

A missing positive blocks publication.

The decision records a missing-positive issue.

Controls cannot satisfy the positive requirement.

### Positive execution failure

A failed positive does not publish.

The decision becomes `block_release`.

The issue codes are retained.

The review queue holds the row.

### Excluded use omission

The policy must state excluded uses.

An empty excluded-use list is a release concern.

The release manifest copies exclusions.

## Quality failures

### Failed evaluation gate

Any failed evaluation check blocks quality.

The gate records the evaluation state.

The release remains blocked.

### Contract gap

Every issue code must be declared.

An unknown issue code fails the gate.

The issue is added to the contract before retry.

### Schema gap

Every operation must have a schema.

An operation gap fails the gate.

The schema must be updated before retry.

### Reconciliation gap

Any mismatch blocks quality.

The mismatched record IDs are retained.

The fixture or evaluator must be corrected.

## Release failures

### Bundle not publishable

An unpublishable policy decision blocks release.

The bundle remains inspectable.

The release state is blocked.

### Replay not accepted

Replay drift blocks release.

The replay comparison identifies fields.

The fixture must be made deterministic.

### Boundary failure

The public boundary is required.

An unexpected boundary blocks quality.

The release does not proceed.

## Queue failures

### Missing queue item

Every execution needs one queue item.

Missing coverage fails the queue.

The record ID identifies the gap.

### Promoted control

Control items must remain held.

A ready control fails the queue.

The issue is not repaired by changing disposition.

### Missing positive readiness

Four positive items must be ready.

Fewer than four ready positives fails the queue.

The failed queue remains inspectable.

### Duplicate queue ID

Queue item IDs must be unique.

A duplicate ID fails the queue.

The item ID includes the record ID.

## Observability failures

### Missing stage event

Ten runtime stages should produce ten events.

A missing event lowers observability.

The event count is checked.

### Missing execution event

Sixteen executions should produce sixteen events.

A missing execution event lowers traceability.

The execution ID identifies the gap.

### Unstable event address

Event content is hashed.

Issue detail is retained.

Execution address is retained in event detail.

## Export failures

### CSV row loss

CSV must contain sixteen data rows.

Controls must be present.

Issue codes must be present.

The export test detects row loss.

### JSON address loss

JSON must retain content addresses.

Canonical export is compared in replay tests.

Missing addresses fail downstream checks.

## Triage order

Inspect the first failed check.

Inspect the corresponding record ID.

Inspect operation and role.

Inspect payload.

Inspect source IDs.

Inspect expected state.

Inspect expected issue codes.

Inspect evaluator output.

Inspect replay drift.

Inspect lineage edges.

Inspect reconciliation items.

Inspect policy decisions.

Inspect quality checks.

Inspect release checks.

Inspect queue items.

## Failure completion

The failure is handled when its issue code is retained.

The failure is handled when its state is expected.

The failure is handled when its control remains visible.

The failure is handled when replay is stable.

The failure is handled when reconciliation passes.

The failure is handled when quality passes.

The failure is handled when the queue is accepted.

The failure is handled when the release boundary remains explicit.

## Non-goals

Failure handling does not infer source truth.

Failure handling does not repair clinical data.

Failure handling does not select treatment.

Failure handling does not rank patients.

Failure handling does not remove disagreement.

Failure handling does not convert review to validation.

Failure handling does not replace institutional governance.
