# Validation Frontier Review Queue

## Purpose

The review queue is the operational handoff for Domain 13 C01–C04.

It turns a deterministic fixture evaluation into a bounded set of review rows.

Each row points to one fixture record.

Each row preserves the operation.

Each row preserves the positive or control role.

Each row preserves the observed state.

Each row preserves issue codes.

Each row has an explicit disposition.

Each row has a priority class.

Each row states the next safe action.

The queue does not claim experimental success.

The queue does not replace the declared assay contracts.

The queue does not remove a control because it is inconvenient.

The queue does not merge distinct failure modes.

The queue is a review artifact built from public aggregate inputs.

## Boundary

The fixture boundary is `public_aggregate_non_patient`.

The fixture context is `GRCh38|glioma|adult|stem_like|core|unknown`.

The queue contains no patient-level row.

The queue contains no personal identifier.

The queue contains no clinical decision.

The queue contains no treatment recommendation.

The queue contains no prognosis statement.

The queue contains no individual risk estimate.

The queue contains no claim of biological validation.

The queue is suitable for method development review.

The queue is suitable for reproducibility review.

The queue is suitable for research triage.

The queue is suitable for bounded planning review.

The queue is not a clinical output.

## Queue model

The queue identifier is stable for a named run.

The fixture identifier binds the queue to its source fixture.

The item identifier uses the form `review:<record_id>`.

The record identifier is copied from the fixture.

The operation is one of four values.

The four operation values are `evidence_gap`.

The four operation values are `assay_eligibility`.

The four operation values are `mpra_planning`.

The four operation values are `starr_seq_planning`.

The role is either `positive` or `control`.

The disposition is either `ready_for_review` or `hold_for_repair`.

The priority is `evidence`, `routing`, `design`, or `control`.

The observed state comes from the operation evaluator.

The issue codes come from the declared contract vocabulary.

The rationale explains why the row has its disposition.

The next action explains what a reviewer should do next.

The content address covers all item fields.

## Disposition rules

An item is ready when its role is positive.

An item is ready when its execution is accepted.

An item is ready when its operation policy is not blocked.

All three conditions must hold.

A positive row with an issue code is not ready.

A positive row with a failed execution is not ready.

A control row is never ready.

A control row remains held even when its state is expected.

An expected control is evidence that a blocker remains visible.

The queue therefore contains four ready rows.

The queue therefore contains twelve held rows.

The queue is accepted only when its structural checks pass.

Queue acceptance does not turn a held row into a ready row.

Queue acceptance means the queue is internally coherent.

## Priority rules

Control rows receive `control` priority.

The C01 positive row receives `evidence` priority.

The C02 positive row receives `routing` priority.

The C03 positive row receives `design` priority.

The C04 positive row receives `design` priority.

Priority is a stable sorting aid.

Priority is not a scientific ranking.

Priority does not imply effect size.

Priority does not imply clinical importance.

Priority does not override an issue code.

Priority does not erase a control.

The next item prefers held rows.

The next item then uses priority.

The next item then uses the item identifier.

The final tie-break is lexical and deterministic.

## C01 evidence-gap review

C01 asks whether a hypothesis has a visible evidence gap.

The positive row carries missing measurement evidence.

The positive row carries uncertainty evidence.

The positive row is partial by design.

The partial state is eligible for planning review.

The first control changes the context.

The second control removes the hypothesis.

The third control supplies a complete snapshot.

The context control must retain `context_mismatch`.

The invalid-input control must retain `invalid_evidence_gap_input`.

The complete control must retain `complete_hypothesis_control`.

The queue does not collapse these into a generic failure.

The queue next action for each control is replay after repair.

The reviewer can distinguish scope repair from evidence repair.

## C02 assay-eligibility review

C02 asks whether an assay can route a declared system.

The positive row matches the declared model system.

The positive row satisfies insert limits.

The positive row contains required controls.

The positive row contains required readouts.

The positive row is ready for route review.

The first control uses a mismatched model system.

The second control omits required controls and readouts.

The third control supplies an empty assay inventory.

The mismatched model retains `model_system_not_available`.

The incomplete capability retains `missing_controls`.

The incomplete capability retains `missing_readouts`.

The empty inventory retains `assay_not_present_in_inventory`.

The queue preserves all three route blockers.

The reviewer can repair inventory or constraint data separately.

## C03 MPRA review

C03 asks whether paired reporter constructs can be planned.

The positive row retains reference and alternate constructs.

The positive row retains negative and positive controls.

The positive row retains the declared model context.

The positive row is ready for design review.

The first control changes the context.

The second control exceeds the construct budget.

The third control supplies no validation targets.

The context control retains `context_mismatch`.

The budget control retains `max_constructs_exceeded`.

The empty-target control retains `no_validation_targets`.

The queue does not treat a planned construct as measured activity.

The queue does not treat a paired design as a positive result.

The queue next action remains review or repair.

## C04 STARR-seq review

C04 asks whether paired STARR-seq constructs can be planned.

The positive row retains reference and alternate inserts.

The positive row retains the same declared model context.

The positive row is ready for design review.

The first control changes the context.

The second control violates insert length.

The third control supplies no validation targets.

The context control retains `context_mismatch`.

The insert control retains `insert_length`.

The empty-target control retains `no_validation_targets`.

The queue keeps C03 and C04 distinct.

The queue does not infer assay equivalence.

The queue does not infer transcript output.

The queue does not infer variant effect.

## Structural checks

`queue:record-coverage` checks execution coverage.

`queue:positive-policy` checks positive readiness.

`queue:controls-held` checks control retention.

`queue:unique-items` checks identifier uniqueness.

`queue:operation-coverage` checks four-operation coverage.

`queue:fixture-binding` checks fixture and evaluation identity.

Every check is content addressed.

Every check has observed and required values.

Every check has a plain detail string.

The queue is accepted only when all six checks pass.

The checks do not use wall-clock time.

The checks do not use random sampling.

The checks do not depend on row ordering.

The checks do not mutate the fixture.

## Review procedure

Load the public fixture.

Run the data audit.

Run the four operation evaluators.

Run the policy decision step.

Build the review queue.

Inspect the queue acceptance flag.

Inspect the ready count.

Inspect the held count.

Inspect the operation counts.

Inspect the issue vocabulary.

Inspect the next item.

Resolve one held issue at a time.

Change the fixture input in a new revision.

Replay the evaluation.

Rebuild the queue.

Compare content addresses.

Record whether the blocker disappeared.

Keep the original control row available for comparison.

Do not delete a control after a repair.

Do not mark a design as measured evidence.

Do not move a row to ready by manual override.

## CLI use

The queue can be emitted from the default fixture.

```text
python -m glio_noncode validation-frontier-review-queue
```

The queue can be emitted from a JSON fixture.

```text
python -m glio_noncode validation-frontier-review-queue fixture.json
```

The queue can be written to a JSON file.

```text
python -m glio_noncode validation-frontier-review-queue --output queue.json
```

The command returns zero for an internally coherent queue.

The command writes one JSON object.

The JSON object contains `queue_id`.

The JSON object contains `fixture_id`.

The JSON object contains `items`.

The JSON object contains `checks`.

The JSON object contains `accepted`.

The JSON object contains `ready_count`.

The JSON object contains `blocked_count`.

The JSON object contains `next_item_id`.

## Example review row

The following shape is illustrative.

```json
{
  "item_id": "review:C02-POS-001",
  "record_id": "C02-POS-001",
  "operation": "assay_eligibility",
  "role": "positive",
  "disposition": "ready_for_review",
  "priority": "routing",
  "state": "ready_for_review",
  "issue_codes": [],
  "rationale": "positive execution satisfies the declared planning policy",
  "next_action": "route to bounded review"
}
```

The example does not assert assay performance.

The example does not assert biological effect.

The example only states that the route passed declared planning checks.

## Example held row

The following shape is illustrative.

```json
{
  "item_id": "review:C02-CTRL-002",
  "record_id": "C02-CTRL-002",
  "operation": "assay_eligibility",
  "role": "control",
  "disposition": "hold_for_repair",
  "priority": "control",
  "state": "blocked",
  "issue_codes": ["missing_controls", "missing_readouts"],
  "rationale": "control or failed execution retains a blocking review condition",
  "next_action": "resolve issue codes and replay"
}
```

The held row is expected.

The held row is not a queue failure.

The held row is a retained boundary condition.

## Determinism

The same fixture produces the same record coverage.

The same evaluation produces the same issue codes.

The same policy produces the same dispositions.

The same queue identifier produces the same content address.

Changing only the queue identifier changes the queue address.

Changing the fixture changes the fixture binding.

Changing a blocker changes the affected item address.

The next item selection is stable.

The issue-code summary is sorted.

The row order follows fixture order for serialization.

The next-item order uses explicit tie-breaks.

The queue has no time-dependent field.

The queue has no random field.

## Failure handling

An empty queue raises a value error.

An empty queue identifier raises a value error.

Missing execution coverage fails a queue check.

Missing positive readiness fails a queue check.

Released controls fail a queue check.

Duplicate item identifiers fail a queue check.

Missing operation coverage fails a queue check.

Fixture and evaluation drift fails a queue check.

A failed queue is still inspectable.

A failed queue should not be published as ready.

The CLI returns a nonzero status when its wrapped operation fails.

The release gate remains the final publish decision.

## Test expectations

The focused review queue test suite checks acceptance.

The focused suite checks all sixteen rows.

The focused suite checks four positive rows.

The focused suite checks twelve control rows.

The focused suite checks four operation views.

The focused suite checks priority assignment.

The focused suite checks next-item selection.

The focused suite checks sorted issue codes.

The focused suite checks serialized counts.

The focused suite checks empty-input rejection.

The focused suite checks queue address behavior.

The focused suite checks item blocker retention.

The focused suite checks deterministic checks.

The focused suite checks replay stability.

The focused suite checks positive issue isolation.

The full suite includes the queue with the other Domain 13 modules.

## Release handoff

Attach the queue JSON to the review bundle.

Keep the queue content address in the release manifest.

Keep the fixture content address in the release manifest.

Keep the evaluation content address in the release manifest.

Keep source receipts in the lineage graph.

Keep all control rows in the evidence export.

Keep the public boundary in the release notes.

Keep excluded uses in the policy output.

Keep the replay receipt beside the queue.

Keep the six structural checks beside the queue.

A release is ready only when the existing quality gate allows it.

The queue is one input to that decision.

The queue is not a replacement for the quality gate.

## Change control

Change the queue module with a focused test.

Change the fixture with a control review.

Change issue vocabulary with a contract update.

Change disposition rules with a policy update.

Change priority rules with a review procedure update.

Change the CLI with a command test.

Change the release shape with a schema update.

Run targeted lint after source changes.

Run focused tests after queue changes.

Run the full suite before a commit.

Run the restricted-metadata scan on staged additions.

Push the exact commit to the protected branch path.

Wait for both Actions lanes.

Record the run URLs in the handoff.

## Traceability summary

The source fixture provides five public receipts.

The source fixture provides sixteen records.

The source fixture provides four positive records.

The source fixture provides twelve control records.

The evaluator produces one execution per record.

The queue produces one item per execution.

The queue produces six structural checks.

The queue produces four ready items.

The queue produces twelve held items.

The queue exposes ten distinct issue codes.

The queue exposes four operation views.

The queue is content addressed.

The queue is replayable.

The queue is bounded.

The queue is review-only.

## Completion criteria

All four positive operations are represented.

All twelve controls remain visible.

All issue codes are declared.

All six checks pass.

The queue content address is present.

The queue fixture binding is present.

The next item is deterministic.

The output is JSON serializable.

The focused tests pass.

The full suite passes.

The staged scan has zero restricted hits.

The CI command passes on the protected branch path.

The resulting queue is ready for bounded review.
