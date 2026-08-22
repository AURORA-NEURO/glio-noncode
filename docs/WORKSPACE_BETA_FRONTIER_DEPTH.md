# Workspace beta frontier depth controls

The base projection classes validate typed objects before they are serialized.
The depth controls validate the package after serialization, where regressions
often appear in a CLI or API boundary.

## Projection assertions

`audit_beta_frontier_projections` checks every execution for:

- output retention and receipt format
- top-level state agreement
- topology node and edge bounds
- focus and warning retention
- causal node and edge shape
- missing mediator sequence shape
- positive and negative receipt fields
- posterior prior, support, proxy, components, shares, residual, and calibration
- table rows, total matches, facets, and warnings

The audit is independent from the release gate. It can therefore report a
serialized-shape failure without mutating the release decision.

## Accessibility checks

`evaluate_beta_frontier_accessibility` checks section labels, descriptions,
reading order, keyboard order, focus boundaries, context retention, review
notes, and check receipts. The report keeps global and surface-specific rows so
a client can render a focused failure summary.

## Public boundary checks

`evaluate_beta_frontier_boundary` checks HTTPS receipts, exact contexts,
operation coverage, role vocabulary, direct-identity key exclusions, row
addresses, output addresses, and the four-positive/twelve-control balance.
These checks are deliberately structural; they do not make a scientific claim.

## Runbook

`default_beta_frontier_runbook` contains 25 ordered commands across prepare,
execute, policy, runtime, release, review, and close phases. Each step declares
the expected exit code, output kind, and failure action. The runbook is a
machine-readable CI contract and a human-readable handoff checklist.

## Cross-surface matrix

`build_beta_frontier_validation_matrix` binds every execution to eight axes:
context, state, receipts, alternatives, reconciliation, pagination, bounds,
and accessibility. The 16-row fixture produces 128 addressed matrix cases.
Pass, review, and hold bands are preserved so a dashboard can distinguish a
successful projection from a projection that requires human inspection.
