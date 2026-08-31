# Comparison-query snapshot registry history observatory

The history observatory turns several persisted comparison-query snapshot
registry histories into one deterministic, reviewable cross-history view. It
answers which histories exist, how many snapshots each contains, what the
latest registry state is, and how the histories changed over time.

This is a local contract over typed data. It does not depend on a remote
service, an older repository, or an installed private dataset. The existing
downloaded-data fixtures are sufficient to exercise the complete path.

## Why this layer exists

A single registry history explains the lifecycle of one registry address. An
observatory adds the next level of comparison:

- each history remains independently addressable;
- each snapshot remains visible as a transition row;
- the latest state and acceptance result are folded into a member row;
- aggregate counts can be checked against every member and transition;
- bounded queries can select summaries, members, transition kinds, or states;
- exact persisted files can be replayed without relying on filesystem order.

The observatory therefore supports both operational review and deterministic
release evidence. A reviewer can start with the summary, move to a history
member, and then inspect its ordered transitions.

## Data model

An observatory has three primary collections.

### Members

One member represents one persisted registry history. Members are sorted by
history identifier and content address. Each member records:

- the history identifier and content address;
- the number of snapshots in that history;
- the latest registry identifier and registry address;
- latest entry, ready, blocked, accepted, rejected, and query-row counts;
- the latest lifecycle state and acceptance result;
- counts for every supported transition kind;
- a derived trend and a canonical member address.

The member address is derived from canonical JSON, so changing any recorded
field changes the address.

### Transitions

One transition represents one snapshot in one history. Transition rows retain
the snapshot ordinal and its prior registry address when a prior snapshot
exists. Rows include the registry metrics, lifecycle state, acceptance result,
transition kind, and canonical transition address.

Transitions are globally ordered by member ordinal and snapshot ordinal. The
first row for a history has no prior registry address. Later rows must have one,
which makes the sequence replayable and catches missing or reordered records.

### Summary

The summary folds the complete member and transition collections. It includes
member and transition totals, state totals, acceptance totals, query-row
totals, and transition-kind totals. The independent audit recomputes these
values rather than trusting the stored summary.

## Exact persistence

The persisted observatory is an exact five-file handoff:

1. manifest.json
2. observatory.json
3. members.json
4. transitions.json
5. summary.json

The manifest lists the three projection artifacts and records their byte
addresses. Persistence writes to a temporary sibling directory and promotes
each complete file atomically. Loading rejects missing files, unexpected
files, non-canonical JSON, broken address linkage, and mismatched nested
artifacts.

The loader also verifies that re-serializing the complete observatory produces
the stored complete address. This makes a copied handoff independently
checkable.

## Independent audits

The aggregate audit has 15 checks:

1. version
2. boundary
3. member order
4. member identity
5. history linkage
6. member counts
7. transition order
8. transition linkage
9. transition counts
10. metric fold
11. state fold
12. acceptance fold
13. artifact linkage
14. public boundary
15. mapping round-trip

The query audit has 11 checks covering resource order, filter replay, count
replay, row order, row addresses, resource semantics, address replay, public
boundary, and mapping round-trip. Both audits return structured check rows,
CSV output, Markdown output, and a boolean acceptance result.

## Bounded query surface

The query surface exposes these resources:

- summary
- members
- empty
- ready
- blocked
- mixed
- transitions
- initial
- improved
- regressed
- unchanged
- changed
- stable

Filters can be combined by history identifier, registry identifier, lifecycle
state, acceptance result, transition kind, derived trend, exact address, and
text. Offset and limit are bounded. Results have stable row ordinals and
canonical row addresses, so a filtered result can be audited independently.

## CLI

The command family uses the long observatory route name already established by
the downloaded-data contract. The base command accepts one or more persisted
history inputs, an observatory identifier, a destination, and an output
format.

The companion commands add:

- aggregate audit;
- bounded query;
- query audit;
- member, transition, manifest, summary, aggregate schema, and capability
  projections;
- audit-check, audit, query-row, query, and query-audit schemas and
  capabilities.

The CLI entry point is:

    python -m glio_noncode

Every public projection is also exercised in continuous integration.

## HTTP

The local API exposes the base observatory route plus /audit, /query, and
/query/audit. Schema and capability routes are available under the same
history-observatory path. Requests use the same typed inputs and bounded query
filters as the CLI, so the two surfaces share validation and address rules.

## Real downloaded-data demonstration

The demonstration script reads the attached GLIO_NONCODE vNext ZIP, extracts
the structured profile members, builds the existing comparison-query registry
history, duplicates the real baseline into a second independently identified
history, and builds this cross-history observatory.

The current demonstration reports:

- 25 archive members;
- 17 selected structured members;
- 4,030 left records and 3,965 right records;
- 160 findings;
- release-ready result: true;
- 2 observatory members;
- 3 ordered transitions;
- latest observatory state: ready;
- 4 total query rows;
- aggregate audit: 15 checks, accepted;
- query result: 9 rows;
- query audit: 11 checks, accepted.

The generated observatory directory contains the exact five files listed
above. The demo also writes aggregate-audit and query-audit projections for
inspection.

## Design invariants

The implementation keeps the following invariants explicit:

- all collections are bounded before construction;
- identifiers and addresses are replayed, not merely copied;
- duplicate history identities are rejected;
- member and transition ordinals are contiguous;
- all summary totals are recomputed from ordered rows;
- persisted JSON is canonical and byte-stable;
- mapping and projection round-trips are tested;
- malformed and tampered handoffs fail closed;
- public schemas and capability metadata describe every exposed operation.

This gives the product a durable cross-history foundation for future
trend analysis, release comparison, and review workflows.
