# Domain 08 C13-C16 evidence gate

This document defines the public aggregate evidence gate for the cell-state
frontier. The gate covers four operations:

| Capability | Operation | Adapter boundary | Accepted output |
| --- | --- | --- | --- |
| C13 | `cell_state_abundance_interval` | `CellStateAbundanceUncertaintyModel` | bounded abundance and interval |
| C14 | `single_cell_reference_mapping` | `SingleCellReferenceMapper` | mapped reference state with margin |
| C15 | `cell_state_ood_detection` | `CellStateOODDetector` | in-domain support finding |
| C16 | `cell_state_context_publication` | `CellStateContextPublisher` | receipt-bound context envelope |

The implementation uses the fixture in
`src/glio_noncode/cell_state_frontier_public_data.py`. It is a deterministic,
public aggregate boundary. It does not contain raw patient records and does not
turn a cell-state observation into a diagnosis, treatment response, prognosis,
or actionability claim.

## Evidence boundary

The fixture context is:

```text
GRCh38|glioma|adult|stem_like|tumor|unknown
```

The evidence boundary is:

```text
public_aggregate_non_patient
```

Every source receipt must use HTTPS, carry a release marker, and name its
aggregate scope. Every record names one or more source receipts. The audit
rejects source IDs that do not resolve, context drift in positive records, and
payload keys that indicate a subject-level identifier.

## Fixture composition

The fixture has 16 records with an intentionally balanced positive/control
matrix:

| Operation | Positive | Controls | Control outcomes |
| --- | ---: | ---: | --- |
| C13 abundance | 1 | 3 | partial, out of domain, partial |
| C14 mapping | 1 | 3 | partial, out of domain, partial |
| C15 OOD | 1 | 3 | partial, out of domain, partial |
| C16 publication | 1 | 3 | partial, out of domain, partial |

The controls are part of the evidence contract. A positive record is accepted
only when its adapter state is `supported`. A control is never allowed to pass
through the supported boundary. The resulting review queue is therefore an
explicit output, not an implicit test failure.

## C13 abundance intervals

C13 delegates interval arithmetic to the existing bounded abundance adapter.
The receipt retains:

- estimate count;
- stable and review IDs;
- abundance values;
- lower and upper interval endpoints;
- observed issue codes;
- exact context and source closure through the surrounding receipt.

The positive record uses a valid count and denominator. One control uses a
negative count, one uses a mismatched context, and one uses an empty
denominator. Each remains visible as a review result. A denominator problem is
not interpreted as zero abundance, absence, or a negative biological finding.

The interval multiplier is declared in the input payload and is never hidden in
the release manifest. The output is descriptive uncertainty around an
aggregate estimate, not a clinical measurement.

## C14 reference mapping

C14 delegates reference score ordering to the supplied score table. The receipt
retains:

- mapping count;
- mapped and review IDs;
- selected reference state IDs;
- top-minus-second margins;
- observed issue codes.

The positive record has a score above the minimum and a margin above the
ambiguity gate. One control has a close top/second pair, one uses a different
context, and one has no scores. The close pair is partial rather than promoted
to a reference state. A missing score table is partial rather than a default
state.

## C15 out-of-domain detection

C15 compares each aggregate finding with two declared support boundaries:
maximum distance and minimum support score. The receipt retains:

- finding count;
- in-domain and OOD IDs;
- review IDs;
- distances;
- support scores;
- observed issue codes.

The positive record is inside both boundaries. One control is distant and has
low support, one has a mismatched territory context, and one has an invalid
distance value. The mismatched territory is reported as `out_of_domain`; the
invalid number is `partial`. Neither outcome is treated as a diagnosis.

## C16 context publication

C16 binds aggregate cell IDs to three upstream addresses:

1. reference mapping;
2. abundance interval;
3. OOD detection.

The positive record publishes only when all three addresses and at least one
cell ID are present. One control has no IDs, one has a mismatched context, and
one is missing an upstream address. Their summaries retain the failure reason
and do not create a release-ready envelope.

## Evaluation contract

`evaluate_cell_state_frontier_fixture` emits seven checks per record:

1. expected state;
2. expected issue floor;
3. context retention;
4. operation contract resolution;
5. positive/control role retention;
6. content address presence;
7. sanitized summary.

It also emits eight global checks:

1. fixture context;
2. record count;
3. positive floor;
4. control floor;
5. operation coverage;
6. source closure;
7. positive state floor;
8. control visibility.

The expected total is 120 checks. A fixture drift that changes an expected state
or issue floor produces a failed check ID tied to the record, while global
boundary failures remain separately addressable.

## Quality gate order

The quality gate runs the following stages in order:

| Stage | Artifact |
| --- | --- |
| data audit | source and payload boundary report |
| evaluation | adapter receipts and checks |
| replay | deterministic state and address replay |
| scenarios | positive/control scenario matrix |
| policy | interpretation and scope checks |
| schema | operation output validation |
| lineage | source-to-receipt edges |
| reconciliation | expected versus observed states |
| bundle | content-addressed release input |

The quality report adds twelve checks for these stages, record floors, check
floor, and metric addressing. The bundle is accepted only if all component
reports are accepted.

## Review and release behavior

The review view sorts rows by priority and then record ID. Out-of-domain rows
receive the highest review priority, while partial rows remain actionable. Each
row includes an action string such as `verify_context_before_reuse` or
`retain_missing_terms_for_review`.

The runtime accepts a run only when the quality bundle is accepted, the optional
requested context matches, and strict review mode is not enabled with visible
review rows. Strict mode is useful for downstream consumers that require an
empty review queue; it does not erase or reinterpret the controls.

The release manifest is `ready` only when both the quality gate and runtime are
accepted. It carries the fixture version, run ID, context key, evidence
boundary, source IDs, operation IDs, quality address, bundle address, and
record address. If any required gate fails, the manifest is `blocked`.

## CLI surface

The full command surface is available without network access because the
default fixture is local and deterministic:

```powershell
glio-noncode audit-cell-state-frontier-data
glio-noncode evaluate-cell-state-frontier-fixture
glio-noncode replay-cell-state-frontier
glio-noncode evaluate-cell-state-frontier-scenarios
glio-noncode cell-state-frontier-policy
glio-noncode cell-state-frontier-contracts
glio-noncode cell-state-frontier-schema
glio-noncode cell-state-frontier-metrics
glio-noncode build-cell-state-frontier-bundle
glio-noncode cell-state-frontier-lineage
glio-noncode cell-state-frontier-reconciliation
glio-noncode run-cell-state-frontier-pipeline --run-id cell-state-frontier-local
glio-noncode build-cell-state-frontier-release --run-id cell-state-frontier-local
glio-noncode cell-state-frontier-review-view
glio-noncode cell-state-frontier-trace --run-id cell-state-frontier-local
glio-noncode export-cell-state-frontier-receipts-csv
glio-noncode export-cell-state-frontier-review-csv
glio-noncode export-cell-state-frontier-review-markdown
glio-noncode export-cell-state-frontier-metrics-csv
```

All serialized JSON, CSV, and Markdown exports omit `input_text` and payload
containers. Raw rows remain available only inside the caller-owned fixture
boundary; receipts and release outputs expose sanitized summaries.
