# Domain 04 C13-C16 reference release frontier API

This package exposes a deterministic, aggregate-only release plane for four
reference and annotation governance capabilities:

| Capability | Operation | Accepted state | Review states |
| --- | --- | --- | --- |
| GNC-D04-C13 | `source_provenance_check` | `accepted` | `review` |
| GNC-D04-C14 | `annotation_drift_detection` | `accepted` | `drift` |
| GNC-D04-C15 | `reproducible_reference_bundle` | `published` | `blocked` |
| GNC-D04-C16 | `reference_release_gate` | `published` | `blocked` |

The public fixture is `reference-release-frontier-public-aggregate`, version
`2026.08.d04-c13-c16.v1`. It contains five public source receipts and sixteen
operation records: one positive and three controls for every operation. The
boundary is `public_aggregate_non_patient`. The fixture carries source URI,
release, license, scope, context, expected state, expected issue codes, and a
content address. It does not contain downloaded reference bytes or
subject-level rows.

## Python entry points

The root package exports the following primary functions:

```python
from glio_noncode import (
    audit_reference_release_data,
    default_reference_release_fixture,
    evaluate_reference_release_fixture,
    run_reference_release_pipeline,
)

fixture = default_reference_release_fixture()
data_audit = audit_reference_release_data(fixture)
evaluation = evaluate_reference_release_fixture(fixture)
pipeline = run_reference_release_pipeline(fixture)
assert data_audit.accepted
assert evaluation.accepted
assert pipeline.accepted
```

The pipeline returns a `ReferenceReleasePipelineReport`. Its `addresses()`
method gives the content address for runtime, release, bundle, artifacts,
review view, queue, observability, accessibility, boundary, invariants,
operational trace, scenarios, thresholds, validation, runbook, and adapter
registry outputs.

## Operation adapters

`SourceProvenanceChecker` checks the public receipt rows for URI, declared
checksum, observed checksum, license, and exact context. A missing URI,
missing license, mismatch, or foreign context remains a review result.

`AnnotationDriftDetector` compares an identity-keyed previous and current
row set. Retrieval-only fields can be ignored. Substantive field changes are
reported with changed field names and a normalized change score. A new row is
drift. Drift is descriptive release evidence and is not a biological effect.

`ReproducibleReferenceBundleBuilder` requires a bundle ID, context, schema
hash, reference identity, and available status. Rows are sorted by reference
ID before the bundle address is calculated. A context mismatch, unavailable
row, missing identity, or missing schema hash blocks assembly.

`ReferenceReleaseGate` evaluates named Boolean checks. The default required
set is `checksum`, `schema`, `license`, `context`, and `source`. Missing and
false checks both block the release and remain in `failed_checks`.

## Report layers

The package separates execution from release packaging:

1. `reference_release_frontier_public_data.py` defines the fixture, source
   receipts, record identities, loader, catalog, and 23 data checks.
2. `reference_release_frontier_contracts.py` defines input fields, output
   fields, states, issue vocabulary, capability IDs, and boundaries.
3. `reference_release_frontier_schema.py` validates field types, required
   values, optional values, list limits, and forbidden output keys.
4. `reference_release_frontier_fixture_eval.py` executes all records and
   emits three checks per record: state, issue vocabulary, and address.
5. `reference_release_frontier_projection_assertions.py` independently checks
   state vocabulary, redaction, schema projection, address, issue vocabulary,
   and accepted-state semantics.
6. `reference_release_frontier_metrics.py` computes operation counts, state
   counts, issue counts, output width, and sanitization status.
7. `reference_release_frontier_lineage.py` builds a redacted source-to-record
   graph and checks dangling edges, node addresses, and execution closure.
8. `reference_release_frontier_policy.py` evaluates twelve named policy rules
   and returns one decision for every execution receipt.
9. `reference_release_frontier_reconciliation.py` compares counts, contexts,
   addresses, policy decisions, graph closure, and projection acceptance.
10. `reference_release_frontier_quality_gate.py` combines the independent
    views into a 25-condition release gate.
11. `reference_release_frontier_replay.py` repeats the fixture and compares
    execution and check tuples plus content addresses.
12. `reference_release_frontier_runtime.py` orders those views into nine
    stages with input and output addresses.
13. `reference_release_frontier_observability.py` records stable stage and
    issue observations without wall-clock or subject-level data.
14. `reference_release_frontier_operational.py` converts the nine runtime
    stages into deterministic work receipts, explicit workload budgets,
    utilization counters, and eighteen operational acceptance checks.

## Projection and safety rules

Execution outputs contain state, IDs, counts, issue codes, summaries, and
addresses. They do not copy `records`, `previous`, `current`, raw rows, or
private material. Metrics and lineage apply the same redaction floor. The
release bundle contains only sanitized receipt rows. The review view retains
all sixteen rows, including controls that are blocked, in drift, or under
review.

Every report has a content address. Prefixes identify the report family:
`sha256:` for canonical fixture and execution receipts, `release-runtime:`
for runtime reports, `release-manifest:` for release manifests,
`release-bundle:` for bundles, `artifact-inventory:` for inventories,
`review-view:` for review tables, and `review-queue:` for queue reports.
Operational receipts use `release-stage-work:`, `release-operational-check:`,
and `release-operational:` prefixes.

## CLI commands

The command family is registered in the root CLI:

```powershell
python -m glio_noncode reference-release-data-audit
python -m glio_noncode reference-release-contracts
python -m glio_noncode reference-release-schema
python -m glio_noncode reference-release-evaluate
python -m glio_noncode reference-release-replay
python -m glio_noncode reference-release-metrics
python -m glio_noncode reference-release-lineage
python -m glio_noncode reference-release-policy
python -m glio_noncode reference-release-quality-gate
python -m glio_noncode reference-release-runtime
python -m glio_noncode reference-release-observability
python -m glio_noncode reference-release-operational
python -m glio_noncode reference-release-release
python -m glio_noncode reference-release-bundle
python -m glio_noncode reference-release-artifacts
python -m glio_noncode reference-release-review-view
python -m glio_noncode reference-release-review-queue
python -m glio_noncode reference-release-accessibility
python -m glio_noncode reference-release-compliance
python -m glio_noncode reference-release-invariants
python -m glio_noncode reference-release-adapters
python -m glio_noncode reference-release-scenarios
python -m glio_noncode reference-release-thresholds
python -m glio_noncode reference-release-validation
python -m glio_noncode reference-release-runbook
python -m glio_noncode reference-release-pipeline
python -m glio_noncode export-reference-release-review-csv
```

Each command accepts an optional JSON fixture path and `--output`. With no
path, the checked-in fixture is used. JSON reports are emitted with stable
indentation; the CSV command emits fixed columns and a terminal newline.
