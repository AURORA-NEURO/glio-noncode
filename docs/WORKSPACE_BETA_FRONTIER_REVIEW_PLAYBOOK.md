# Workspace beta frontier review playbook

## First pass

1. open the release manifest
2. confirm `public_aggregate_non_patient`
3. inspect `hold_reasons`
4. inspect quality blocking failures
5. compare replay addresses
6. open the review queue

## Topology review

Confirm the viewport focus, node and edge bounds, loop and promoter-capture
receipts, source versions, and context warnings. A foreign-context control is
expected to be withheld. A blank viewport is not evidence against a topology.

## Chain review

Confirm the required mediator kinds, edge order, alternative edge IDs, missing
kinds, negative evidence IDs, uncertainty values, and chain state. If the state
is contradictory, review the edge receipts before considering any follow-up
research step.

## Posterior review

Confirm declared prior, evidence support, proxy value, calibration status,
component totals, normalized shares, and residual. A partial decomposition is
the correct result when contributions do not reconcile. A missing support value
must remain abstained.

## Table review

Confirm exact context, record types, channels, tiers, confidence threshold,
offset, limit, total matches, facets, and row states. Compare a paginated page
with the full `total_matches` count. The filter must not rewrite a partial row
as supported.

## Closeout

Close a queue item only after its expected state and issue set are reconciled.
Do not close an item by deleting its control row. The next replay should retain
the same content addresses for unchanged input.
