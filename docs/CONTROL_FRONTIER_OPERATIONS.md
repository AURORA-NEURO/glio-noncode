# Control frontier operations

This document describes the public aggregate runtime for Domain 16 C05-C12.
The package is intentionally a bounded operational surface. It validates
declared contracts, routes control paths, and retains receipts. It does not
interpret aggregate results as clinical or biological findings.

## Shared contract

Every fixture row contains:

- a stable row identifier;
- one of the eight operation names;
- a positive or control role;
- the exact context key;
- one or more source receipt identifiers;
- an operation-specific payload;
- an expected state and issue-code tuple;
- a short boundary note; and
- a SHA-256 content address.

The runtime accepts a positive row only when the observed state equals the
declared expected state and the observed issue tuple is empty. A control row
is useful when it remains visible and is not silently treated as success.
Five checks are retained for every row: state, issue vocabulary, role
separation, receipt addressing, and structured output.

## C05 policy and claim gate

The policy adapter is deny-by-default. It checks the exact context, source
allowlist, mutation scope, sensitive-key paths, network sources, and claim
ceiling. It returns an explicit state and issue tuple, and it never includes
the raw value of a sensitive field in a receipt.

The positive case declares an aggregate input, a public source, no mutation,
and a descriptive claim ceiling. Controls exercise a sensitive path, a source
outside the allowlist, and an unapproved mutation. The control output keeps
the issue code while only exposing the path or category required for review.

## C06 budget and resource scheduler

The scheduler adapter receives typed work items with dependency IDs and
resource requests. It checks topological order, CPU, memory, GPU, storage,
network, wall-clock, and cost budgets. A cycle is a hard boundary. A work item
that exceeds capacity is retained as a rejection; optional network work is
retained as deferred work.

The scheduler is deterministic for a fixed fixture: stable work IDs are used
as the final tie breaker after dependency readiness and priority. The adapter
does not start a process or contact a service. It only returns the schedule
receipt needed by the later execution surface.

## C07 deterministic fallback

The fallback adapter evaluates candidates in declared priority order. A
candidate must be eligible, retryable for the current failure, deterministic,
permitted by the network boundary, complete for required inputs, compatible
with the output contract, and within remaining cost. Each rejection is kept in
the output so route selection can be audited.

The positive case selects the highest eligible local candidate. Controls cover
a non-retryable error, a network-only candidate, and a missing-input route.
When no candidate is eligible, the state is abstained and the issue is
`no_eligible_candidate` rather than a fabricated result.

## C08 human review router

The review adapter transforms blocked, abstained, non-retryable, and explicitly
review-required outcomes into bounded queue items. Priority is stable, roles
are declared, source IDs remain attached, and omitted rows are recorded when a
queue limit is reached. An empty queue is a valid explicit state.

The queue, SLA report, handoff report, CSV export, and Markdown report all use
the same row IDs and content-addressed receipt chain. The implementation does
not invent reviewer identity or adjudication outcome.

## C09 execution ledger

The ledger adapter replays a typed event history. It checks event identity,
context identity, contiguous sequence, allowed transitions, terminal state,
and duplicate IDs. A foreign context is out of domain even when its event
sequence is otherwise valid.

The audit log and replay modules project the same execution into separate
verification surfaces. The runtime retains transition issues instead of
rewriting the original event history.

## C10 model registry

The model adapter resolves an exact model ID and version. It compares context
support, input contract, output contract, status, artifact digest, license,
and evaluation receipt. A missing version abstains; a foreign context or
contract mismatch is explicit.

Compatibility evidence means registry metadata is coherent. It is not a
performance assessment and does not authorize a scientific conclusion.

## C11 data/reference registry

The reference adapter resolves a dataset version by ID, exact context,
coordinate system, license, status, checksum, schema hash, source URI, and
retrieval receipt. Unsupported context, coordinate mismatch, restricted
license, and missing dataset controls each retain a separate issue code.

The source registry and data dictionary provide stable names for the same
fields across JSON, CSV, and report projections.

## C12 drift and out-of-domain monitor

The monitor adapter compares a declared reference value and current value to
watch and drift thresholds. It keeps in-domain support, support score, source
IDs, and a raw observation hash. Watch, drift, and out-of-domain states are
distinct. An out-of-domain observation is not transported into the accepted
path.

## Runtime ordering

The runtime order is intentionally stable:

1. data audit;
2. schema validation;
3. adapter construction;
4. fixture evaluation;
5. metrics;
6. lineage;
7. policy;
8. reconciliation;
9. review queue;
10. quality gate;
11. replay;
12. release;
13. package manifest;
14. compliance;
15. projection assertions;
16. control coverage;
17. performance budget;
18. compatibility;
19. support directory;
20. source registry;
21. access manifest;
22. benchmark;
23. audit log;
24. evidence and depth closure.

The stages are pure projections over the fixed fixture. A stage failure is
retained in the runtime report and prevents an accepted release receipt.

## Output boundaries

JSON is the canonical machine-readable form. CSV contains reviewable rows and
metrics only. Markdown is a human-readable summary of counts, states, issue
codes, and boundaries. All outputs are derived from the same in-memory
evaluation and retain the fixture ID and context key.
