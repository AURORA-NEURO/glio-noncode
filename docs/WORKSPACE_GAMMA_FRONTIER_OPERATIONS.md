# Workspace Gamma Frontier Operations

## Purpose

The C09–C12 package is operated as a local, inspectable quality-gated report.
The default path uses only the public aggregate fixture. External systems may
provide a JSON fixture, but the same contracts, source receipt checks, exact
context gate, issue vocabulary, and release checks apply.

## Normal sequence

1. Run the data audit.
2. Inspect contracts and schema.
3. Evaluate positive and control rows.
4. Run replay.
5. Inspect metrics, lineage, and policy.
6. Run reconciliation and projection assertions.
7. Run the runtime and quality gate.
8. Build the release manifest.
9. Inspect the review queue.
10. Export the compact review table.

The end-to-end command performs the same sequence and returns all intermediate
addresses.

## Data audit

The data audit requires five HTTPS source receipts, sixteen records, four
positive records, twelve controls, four operations, and one declared context.
Any failed check is retained by ID. Data audit failure is a blocking release
condition.

## Runtime rehearsal

The runtime report is the primary operational object. It contains the fixture
ID, ordered stage receipts, data audit, evaluation, metrics, policy decisions,
lineage graph, reconciliation, projection audit, quality gate, and a final
content address.

Each stage has an input address list, output address, state, detail, and stage
address. Stage order is stable. A stage may be `complete`, `accepted`, or
`blocked`; no stage silently disappears.

## Review routing

The default policy has ordered rules:

1. foreign context is held;
2. blocked, denied, or abstained outputs are held;
3. expired snapshots are held;
4. rows with issue codes require review;
5. ready or review-required rows require review;
6. clean verified snapshots may be released;
7. clean allowed access may be released;
8. clean boards remain review-only.

The default rule is hold. A new state cannot become releasable merely by being
added to an enum.

## Review queue

Queue priority is:

- `1` blocking;
- `2` context;
- `3` issue;
- `4` informational.

Rows with release decisions are omitted from the required queue. Every queued
row includes a reason, issue codes, disposition, and content address. Queue
checks confirm that all row addresses are present and that release state is
visible.

## Monitoring

Observability emits one `stage_completed` event per runtime stage and one
`record_evaluated` event per execution. Warning severity indicates retained
issue evidence. Error severity indicates a blocked runtime stage. Event order
is stable and each event has an address.

Recommended counters:

- total records;
- positive records;
- control records;
- passed checks;
- failed checks;
- rows with issue evidence;
- held rows;
- queued rows;
- replay match status;
- quality-gate status.

## Safe output handling

Use the compact manifest or review CSV when sending results to a review system.
The bundle contains addresses, not raw secrets. The snapshot publisher output
contains the signed envelope for local verification, but the compact execution
view intentionally omits signing material.

Do not place secrets in fixture JSON. Use an external secret source when
calling `ShareableSnapshotPublisher` directly. Treat `key_id` as a reference,
not as secret material.

## Failure response

### Data audit failure

Stop release packaging. Inspect the failed data check, source URI, expected
count, and context. Correct the fixture or source receipt and rerun evaluation.

### Evaluation failure

Inspect the row check for state and issue mismatch. Confirm that the primitive
surface still emits explicit state and issue evidence. Do not change the
expected control merely to make the gate green.

### Replay mismatch

Inspect the differing evaluation and execution addresses. Look for volatile
timestamps, unordered mappings, non-canonical values, or hidden environment
inputs. Repeated evaluation must use the same observable output contract.

### Quality-gate failure

Read the blocking check list. A release is not ready while data, evaluation,
reconciliation, projection, or boundary evidence is missing.

### Review queue growth

Queue growth is an observable state, not an error by itself. Group by operation,
issue code, context mismatch, and policy rule. Resolve the underlying evidence
or document the hold decision.

## Capacity boundaries

The threshold module declares inspectable nominal ranges. These thresholds are
operational bounds, not scientific cutoffs. Exceeding a threshold should create
a review signal and never be interpreted as biological significance.

## Release checklist

- [ ] Data audit accepted.
- [ ] Four operations covered.
- [ ] Four positives and twelve controls retained.
- [ ] All expected states and issues reconciled.
- [ ] Projection assertions accepted.
- [ ] Boundary checks accepted.
- [ ] Replay addresses match.
- [ ] Review queue inspected.
- [ ] Release state is `ready`.
- [ ] Bundle and artifact inventory are addressed.
- [ ] CSV and JSON exports are generated from the same view.
