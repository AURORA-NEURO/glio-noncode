# Workspace beta frontier scenario guide

The scenario matrix is a compact contract for boundary behavior. Each
operation has eight dimensions, and each dimension has a named expectation.
The guide below describes how to interpret the matrix in review tooling.

## Context scenarios

Exact-context rows should render their projection output. Foreign-context rows
should retain a context issue and should not be promoted. A context mismatch is
different from an absent observation: one confirms that data exists elsewhere,
while the other confirms that no matching data was supplied.

## State scenarios

Supported and complete rows can be summarized under the declared research
policy. Partial and incomplete rows should show visible limitations. Absent and
abstained rows should show missingness rather than a negative result.
Contradictory rows should show both the conflict and the evidence receipts.

## Receipt scenarios

Every output receipt must use the `sha256:` prefix. Source IDs and versions are
separate fields and should not be merged into display text. A review client can
use the content address as a stable link to a cached result.

## Alternative scenarios

The causal chain fixture includes a primary element-to-gene path and an
alternative target. Both remain edges. The matrix selects `multiple` without
assigning a preferred path or adding a combined score.

## Reconciliation scenarios

The supported posterior fixture has two components whose total equals declared
support. The foreign-component and unreconciled controls preserve the local
components, report the residual, and remain partial. The matrix makes that
difference visible without changing the posterior primitive.

## Pagination scenarios

The table pagination control uses a non-zero offset. The page is smaller than
the full match set, but `total_matches` and facets still describe the complete
filtered set. A client must not infer that the page is the whole result.

## Bound scenarios

Topology and table outputs have explicit bounds. A boundary case is a review
signal, not a silent truncation. The operation output should retain warnings or
the bounded count so a user can distinguish a complete view from a clipped one.

## Interaction scenarios

The table workspace carries section labels, descriptions, and order. Review
rows carry notes. These fields are part of the serialized contract and should
remain available in CLI, API, notebook, and graphical clients.

## Matrix review questions

- Does every execution have eight matrix cases?
- Is the exact context shown on every case?
- Are foreign rows held rather than discarded?
- Are partial states counted separately from absent states?
- Are contradiction and alternative paths distinguishable?
- Does the table preserve total matches after pagination?
- Does every case link to an execution address?
- Does a replay retain the same case and report addresses?

The answers should remain stable for an unchanged public fixture. A change to
any answer requires a new review note and a new content address.
