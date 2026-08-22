# Workspace beta frontier validation matrix

The validation matrix is the post-serialization view of Domain 15 C05-C08.
It connects every fixture execution to eight cross-surface dimensions:

1. context qualification
2. state preservation
3. receipt retention
4. alternative paths
5. reconciliation
6. pagination
7. output bounds
8. interaction metadata

The matrix is intentionally separate from the operation evaluator. The
evaluator answers whether a projection produced its expected state. The matrix
answers whether that result still has the fields and evidence needed by a
release consumer after serialization.

## Case construction

Each of the 16 fixture rows is paired with each of the eight axes. This yields
128 addressed validation cases. A case contains:

- a stable case ID
- the source record ID
- the operation
- the axis and selected value
- pass, review, or hold status
- observed state
- issue codes
- the execution content address
- a human-readable detail string

The result keeps all cases, including controls. It does not reduce the matrix
to a single score.

## Status bands

`pass` means the execution is structurally ready for that axis. `review` means
the execution is valid but has a partial, incomplete, absent, abstained, or
paginated state that should remain visible. `hold` means foreign context,
contradiction, or invalid input prevents promotion under the current boundary.

This is a review classification, not a scientific conclusion.

## Context axis

The context axis is exact. A row with `context_mismatch` selects `foreign`.
The matrix retains the row and its execution receipt. A client must not replace
the row with an empty success response.

## State axis

The state axis uses the serialized state from the projection. It preserves:

| State | Matrix interpretation |
| --- | --- |
| supported | exact inputs meet the projection contract |
| partial | visible inputs remain unresolved or unreconciled |
| absent | no matching observation or row exists |
| abstained | a required measurement was not declared |
| contradictory | exact-context inputs disagree |
| out_of_domain | requested context does not match |
| invalid | input failed structural validation |

## Receipt axis

The receipt axis checks the `sha256:` format on execution addresses. Source
receipt checks remain in the boundary report. A structural output with no
receipt is not considered complete for a release client.

## Alternative-path axis

The causal chain surface selects `multiple` when more than one alternative
edge ID is present. All other rows select `single`. The selection is
descriptive and does not rank one path above another.

## Reconciliation axis

Posterior rows select `residual` when `unreconciled_components` is present.
Other rows select `matched`. The matrix preserves the posterior residual and
the original issue set for a reviewer.

## Pagination axis

Evidence-table rows select `paged` when a non-zero offset was applied. The
table output must retain `total_matches` and pre-pagination facets. A client
that only renders the page cannot claim that the result set contains one row.

## Bounds axis

Valid projection outputs select `within`; malformed focus or input selects
`boundary`. The operation-specific assertion layer checks topology node and
edge limits and table page limits independently.

## Interaction axis

Positive rows select `labeled`; control rows select `review`. The separate
accessibility report checks section labels, descriptions, order, focus
boundaries, and review notes. This separation allows a client to report an
interaction defect without rewriting scientific state.

## Consumer checklist

- load the matrix report before rendering a release summary
- display pass, review, and hold counts separately
- provide a filter by operation and axis
- link each case to its execution address
- show issue codes without converting them to a negative result
- show the exact context for every selected row
- retain the fixture and package version
- block release only on the declared blocking report

## Replay behavior

The matrix is deterministic because its case IDs, selected values, status
rules, and detail strings depend only on the fixture execution. A replay of the
same fixture should produce the same report content address. A changed issue
set or execution state should change the matrix address and surface a review
difference.
