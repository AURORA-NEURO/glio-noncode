# Sequence frontier release format

## Release contents

`build_sequence_frontier_release` returns a deterministic manifest that joins
the quality report and runtime result. The manifest contains:

| Field | Meaning |
| --- | --- |
| `release_id` | Content-addressed release identity |
| `fixture_id` | Checked-in evidence fixture identity |
| `run_id` | Runtime invocation identity |
| `context_key` | Exact reference, disease, age, state, territory, treatment context |
| `evidence_boundary` | `public_aggregate_non_patient` |
| `quality` | 11-check quality report and content address |
| `runtime` | Stage receipts, evaluation, policy, lineage, reconciliation, and exports |
| `bundle` | C13-C16 record and source bundle address |
| `release_state` | `ready` or `blocked` |
| `content_address` | Hash over the complete manifest |

The release ID changes when any declared fixture, source receipt, contract,
evaluation output, or runtime stage changes. Run IDs are supplied by the caller
so independent reruns can be compared without changing the fixture identity.

## Runtime result

The runtime result keeps separate objects for:

- source data audit;
- evaluation report and 120 checks;
- policy report and its rules/checks;
- quality report and 11 checks;
- replay report and expected content addresses;
- scenario matrix report;
- lineage report with source-to-release edges;
- reconciliation report with count and address comparisons;
- metrics report with operation-level state counts;
- review view and sanitized export receipts;
- nine-stage observability trace.

The result is serializable through the package JSON conversion boundary. CSV and
Markdown exports are derived from the typed view and contain record IDs,
operation, state, priority, issue codes, context, and review detail. They do not
include raw sequence text, raw external response bodies, or subject identifiers.

## Release readiness

A release is `ready` only when:

1. the fixture identity is the expected checked-in version;
2. all source IDs resolve to receipts;
3. every operation has one positive record and three controls;
4. evaluation, policy, schema, replay, lineage, and reconciliation pass;
5. the C16 publication bundle is complete;
6. review entries remain visible with priority and issue codes;
7. export sanitization checks pass;
8. no stage reports a failed check;
9. the final manifest content address verifies.

The default runtime permits review controls while retaining them in the result.
`--fail-on-review` changes the runtime boundary for batch use: any review state
causes the run to be unsuccessful, but the full diagnostic result is still
returned for inspection.

## Reproducibility

The fixture is immutable by convention and loaded from JSON only after its
schema and content address are validated. Replay compares expected operation
states, check counts, receipt addresses, bundle address, and release inputs.
The runtime does not perform network retrieval, so a rerun with the same source
file and run options produces the same scientific evidence objects.
