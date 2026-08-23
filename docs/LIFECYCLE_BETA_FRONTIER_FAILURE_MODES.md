# Lifecycle Beta Frontier Failure Modes

The aggregate package is designed to make failure states inspectable.

| Failure | Expected state | Required action |
| --- | --- | --- |
| Missing parent claim | partial | resolve lineage or retain the hold |
| Foreign context | out_of_domain | exclude from the requested context |
| Directional tier conflict | contradictory | preserve both directions for review |
| Out-of-range uncertainty | partial | quarantine the invalid observation |
| Missing decision | review_required | obtain the declared decision count |
| Split verdict | split_decision | route to adjudication |
| Duplicate review ID | partial | reject the append and retain the previous log |
| Blocking release gate | review_required | hold the research release |
| Explicit rejection | rejected | preserve the rejection receipt |
| Changed snapshot | review_required | reconcile before release |

No failure mode is converted to success by averaging or by a positive row in a
different operation. The quality gate, replay receipt, depth audit, and release
manifest all retain their own content addresses. A changed fixture, schema,
policy, or adapter produces a new address and requires a new review record.

The operational recovery sequence is:

1. preserve the last successful stage addresses;
2. identify the first failed check or invariant;
3. inspect the corresponding positive/control rows;
4. correct the source, schema, or adapter at its declared boundary;
5. rerun data audit, evaluation, reconciliation, quality, and replay;
6. rebuild the handoff and research-only release manifest.

If the context key is wrong, stop before any aggregation. If a source receipt
is missing, stop before release. If a reviewer decision is split or absent,
keep the case in the review queue. If a content address changes, do not
overwrite the prior artifact.

## Access and output boundary

The access manifest names six stable aggregate surfaces: fixture JSON,
evaluation JSON, review CSV, metrics CSV, trace JSON, and release JSON. Every
surface retains the `public_aggregate_non_patient` boundary. The manifest also
states whether controls are supported, so consumers cannot accidentally treat
the positive rows as the whole fixture.

The access audit reports `boundary-mismatch`, `patient-level-data`,
`controls-hidden`, and `duplicate-surface-id`. These are release blockers. A
successful operation evaluation does not override an access failure.

## Evidence and audit chain

The evidence matrix creates six completeness planes for every execution:
context, source, operation, state, control, and address. A missing cell is an
explicit failure, not an empty value silently omitted from a projection.

The runtime stage audit is hash-linked. The first event points to
`sha256:genesis`; each later event points to the preceding event address. The
verifier checks sequence, predecessor, and recomputed event address. This
makes stage reordering and edited audit history observable.

## Performance signal

The benchmark surface measures fixture evaluation and record-address scanning.
Its records-per-second value is a regression signal for local implementation
work, not a scientific result. A benchmark failure means the implementation
needs review; it does not change the evidence state of the fixture.
