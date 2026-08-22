# Workspace Gamma Frontier Validation

## Test layers

The test suite is intentionally layered so a failure identifies a contract
boundary rather than only a final boolean.

### Primitive layer

The existing workspace primitives are tested for card grouping, launch
planning, HMAC verification, and role-based access. The C09–C12 package calls
those primitives with public fixture mappings.

### Fixture layer

The fixture evaluator runs all sixteen rows and records three checks per row:

1. expected state;
2. expected issue set;
3. content-addressed execution receipt.

The default fixture therefore has forty-eight row checks. A clean run reports
all forty-eight as passed.

### Projection layer

Projection assertions inspect serialized output fields independently of the
primitive implementation. Board rows must preserve six columns and graph
fields. Launch rows must preserve parameter hashes and network policy. Snapshot
rows must preserve verification dimensions. Access rows must preserve policy
receipts and reasons.

### Evidence layer

Lineage checks connect sources to fixture, fixture to records, records to
executions, and executions to output field addresses. Reconciliation compares
the fixture expectation with the observed state and sorted issue set.

### Release layer

The quality gate requires data audit, fixture evaluation, contract coverage,
schema coverage, lineage nodes, lineage edges, reconciliation, projection
assertions, public boundary, and control retention. Release checks add replay,
address equality, and a minimum row count.

## Scenario dimensions

Each operation appears in five scenario dimensions:

| Dimension | Expected handling |
| --- | --- |
| accepted | bounded in-context result |
| foreign_context | explicit out-of-domain result |
| malformed | retained abstention or invalid issue |
| boundary | explicit review state |
| replay | stable content addresses |

The matrix has twenty scenarios. The matrix is a declaration of coverage. The
fixture evaluator is the executable check of concrete rows.

## Validation axes

The validation matrix has seven axes for every operation:

- exact context;
- schema;
- negative evidence;
- content address;
- research boundary;
- accessibility;
- replay.

The default matrix has twenty-eight passing cases. A case is complete only when
every required evidence token appears in the observed evidence list.

## Accessibility checks

Accessibility checks require a row for every operation, visible state text,
stable addresses, and board column output. Board columns are created with an
accessible label and description by the underlying board builder.

## Boundary checks

Boundary checks require the aggregate non-patient declaration, HTTPS source
receipts, no signing secret or verification secret in serialized execution
outputs, and research-use snapshot status. An advisory check ensures raw field
names do not leak into the compact output.

## Invariants

The invariant report checks:

- four-operation coverage;
- one positive plus three controls per operation;
- addressed executions;
- non-empty states;
- issue evidence on every control;
- unique record IDs.

Invariants are separate from the quality gate so they can be inspected during
development without changing promotion logic.

## Replay expectations

Replay compares the evaluation address and every execution address. The
snapshot primitive emits a current issue time internally, but the compact
execution output intentionally omits that volatile value. This keeps the
review contract reproducible while leaving the full envelope available to a
direct caller for local verification.

## Test commands

```powershell
$env:PYTHONPATH = "src"
python -m unittest tests.test_workspace_gamma_frontier tests.test_workspace_gamma_frontier_cli -v
python -m compileall -q src/glio_noncode
ruff check src/glio_noncode/workspace_gamma_frontier_*.py tests/test_workspace_gamma_frontier*.py
```

The full repository suite remains required before release. The focused suite
is useful during a module-by-module build.

## Acceptance record

A release candidate is accepted only when:

```text
data_audit.accepted == true
evaluation.accepted == true
runtime.quality.accepted == true
replay.accepted == true
release.state == ready
bundle.accepted == true
artifact_inventory.accepted == true
review_queue.accepted == true
accessibility.accepted == true
boundary.accepted == true
invariants.accepted == true
validation_matrix.accepted == true
```

The end-to-end pipeline evaluates this set and stores the aggregate result in
`GammaFrontierPipelineReport.accepted`.
