# Domain 04 C13-C16 operations and runbook

## Runtime stages

`run_reference_release_runtime` executes nine ordered stages. Every stage
records its sequence, stage ID, input addresses, output address, state, and
detail string.

| Sequence | Stage | Main output | Gate behavior |
| ---: | --- | --- | --- |
| 1 | `data-audit` | `ReferenceReleaseDataAudit` | Count and source closure. |
| 2 | `fixture-evaluation` | `ReferenceReleaseEvaluation` | All positives and controls execute. |
| 3 | `metrics` | `ReferenceReleaseMetricsReport` | Counts and redaction floors. |
| 4 | `policy` | `ReferenceReleasePolicyReport` | Twelve named policy rules. |
| 5 | `lineage` | `ReferenceReleaseLineageGraph` | Source-to-receipt graph. |
| 6 | `projection-audit` | `ReferenceReleaseProjectionAudit` | Output schema and redaction. |
| 7 | `reconciliation` | `ReferenceReleaseReconciliation` | Cross-view count and identity closure. |
| 8 | `quality-gate` | `ReferenceReleaseQualityGate` | Twenty-five independent conditions. |
| 9 | `replay` | `ReferenceReleaseReplayReceipt` | Repeat execution and address comparison. |

The runtime is accepted only when the data audit, evaluation, policy,
projection audit, reconciliation, quality gate, and replay all pass. A failed
stage is retained; later packaging cannot turn it into a ready release.

## Policy rules

The policy module keeps twelve named rules:

1. Public aggregate boundary.
2. Exact context required.
3. URI and checksum visible.
4. License required.
5. Drift remains descriptive.
6. Ignored receipt fields stay ignored.
7. Available rows only.
8. Bundle context exact.
9. Bundle is content addressed.
10. Required checks explicit.
11. Failed checks itemized.
12. No hidden mutation.

Every execution receives one policy decision. An allowed decision routes to
`publish`; a failed rule routes to `review` and retains the failed rule IDs.
The policy report itself is accepted when all rules and decisions are
well-formed, even though controls correctly produce review decisions.

## Lineage

The lineage graph includes one fixture node, five source nodes, sixteen record
nodes, sixteen execution nodes, forty-eight check nodes, sixteen output nodes,
and issue nodes for every retained issue. The accepted fixture currently
produces 111 nodes and 133 edges. Node attributes contain source identity,
release, URI, scope, operation, role, state, counts, and check detail. Raw
operation payloads are excluded.

The graph audit checks unique node IDs, dangling edges, node address prefixes,
raw-key exclusion, and execution closure. The reconciliation layer also
requires at least 100 nodes and 100 edges so an accidentally shallow graph
cannot satisfy the release gate.

## Review queue

The review view retains all sixteen records. The queue selects every blocked,
drift, or review row, and also retains any row that is not accepted. Rows are
ordered by descending priority and then record ID. Provenance failures route to
`inspect-source-receipts`; drift, bundle, and release failures route to
`inspect-release-boundary`.

The queue does not delete controls after a release is ready. It is a separate
operational projection used to inspect the evidence that the accepted bundle
intentionally excludes.

## Observability

Observability records stage states, execution-state counts, and issue-code
counts. Each observation has a stable address and a severity. The report
contains no raw rows. The counter map includes the stage count, execution
count, check count, positive/control counts, state counts, and issue counts.

## Runbook

The checked-in runbook contains fourteen steps:

1. Inspect refs and the worktree.
2. Run the data audit.
3. Validate contracts.
4. Validate schemas.
5. Evaluate all records.
6. Replay the evaluation.
7. Evaluate policy.
8. Build lineage.
9. Run the quality gate.
10. Run the nine-stage runtime.
11. Build the accepted bundle.
12. Build the review queue.
13. Run the local test suite.
14. Push the exact commit and inspect hosted Actions.

Every step states its purpose, expected result, and failure action. The
runbook requires preservation of failed controls and forbids replacing a
review state with a guessed source value.

## Efficient local commands

```powershell
$env:PYTHONPATH = 'src'
python -m unittest tests.test_reference_release_frontier tests.test_reference_release_frontier_cli -v
ruff check src/glio_noncode/reference_release_frontier_*.py tests/test_reference_release_frontier*.py
python -m compileall -q src tests
python -m glio_noncode reference-release-pipeline
```

The complete repository suite remains the release gate for a commit. The
focused commands are the fast feedback loop while editing the package.
