# Workspace beta frontier failure modes

## Foreign context

The requested context and the evidence context are compared exactly. Foreign
topology observations are withheld from the viewport. Foreign mediator results
are withheld from the chain. Foreign posterior components are withheld from
the decomposition. A table filter with a foreign context returns an empty
out-of-domain view.

## Invalid topology focus

Focus start and end must be a complete interval with a positive start and
start less than or equal to end. A malformed focus is reported as
`invalid_projection_input`; it is not treated as an empty topology.

## Missing mediator

The causal explorer returns an incomplete chain and lists every missing
required mediator kind. A missing link is not inferred from neighboring edges.

## Contradictory mediator

An against-direction or contradictory result remains attached to its edge. The
chain state becomes `contradictory` when the exact-context edge carries an
ambiguous state.

## Posterior residual

The posterior view calculates:

```text
residual = evidence_support - sum(exact_context_contributions)
```

When the absolute residual exceeds tolerance, the view is `partial`. A foreign
component is excluded from the exact-context total and a warning is retained.

## Empty table

An empty table is `absent` and carries `no_matching_rows` in the fixture
evaluation. The table facets remain present as empty maps, allowing a client to
distinguish no matches from a missing response.

## Pagination

Pagination changes the returned page, not `total_matches` or the pre-page
facets. The evaluation retains `pagination_applied` for a non-zero offset.

## Serialization failure

Invalid input is caught at the fixture boundary and represented as an
`invalid_projection_input` execution with its error text. The surrounding
runtime can continue to produce a complete audit package.
