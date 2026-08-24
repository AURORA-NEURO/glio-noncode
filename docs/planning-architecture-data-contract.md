# D13 Data Contract

## Aggregate envelope

The top-level fixture requires `fixture_id`, `version`, `boundary`,
`context_key`, `foreign_context_key`, `family_contexts`, `sources`,
`operations`, `cases`, and `content_address`.

The boundary is `public_aggregate_non_patient`. The envelope context is
`multi_context_public_aggregate`; each family context is retained separately
and each case records both its envelope context and its delegate context.

## Sources

Each source row records the prefixed aggregate source ID, family, source kind,
source version, URI, delegate source ID, delegate fixture ID, public aggregate
flag, delegate content address, and aggregate content address. Case and
operation source joins must resolve to these twenty rows.

## Cases

Each case records the operation and capability IDs, ordinal, family, plane,
scenario, input and output contracts, dependency context, delegate fixture and
record IDs, source IDs, sanitized payload, expected observed state, expected
issue codes, bounded count invariants, description, and content address.

The four scenarios are `positive`, `control_a`, `control_b`, and `control_c`.
The expected state and issue vocabulary are sourced from the evaluated family
delegate, so context mismatch, review, rejected, blocked, and abstained paths
cannot disappear during aggregation.

## Release rules

The release is published only when schema joins, data audit, operation plan,
delegate evaluation, review routing, replay, lineage, ledger, metrics,
artifacts, quality, and public-boundary compliance close. The release remains
a planning projection and carries explicit limitations.
