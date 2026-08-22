# Domain 08 release format

The Domain 08 release manifest is the final structured boundary for the
cell-state frontier. It is produced by
`build_cell_state_frontier_release` after the quality bundle and runtime have
both been evaluated.

## Manifest fields

| Field | Description |
| --- | --- |
| `release_id` | deterministic release identifier derived from manifest inputs |
| `fixture_id` | public aggregate fixture identity |
| `fixture_version` | fixture contract version |
| `run_id` | caller-selected runtime run identifier |
| `context_key` | exact reference and biological context |
| `evidence_boundary` | `public_aggregate_non_patient` |
| `release_state` | `ready` or `blocked` |
| `quality_address` | address of the twelve-check quality report |
| `bundle_address` | address of the complete evidence bundle |
| `record_address` | address of the receipt collection |
| `source_ids` | ordered source receipt IDs |
| `operation_ids` | ordered unique operation IDs |
| `content_address` | address of the final manifest body |

The `accepted` convenience property is true only when `release_state` is
`ready`.

## Ready state

A release is ready only when all of the following are true:

1. public aggregate data audit passes;
2. all 16 fixture records execute;
3. all 120 evaluation checks pass;
4. the replay report passes all eight checks;
5. all 16 scenario checks pass;
6. all twelve policy checks pass;
7. all 23 schema checks pass;
8. lineage closes over all source receipts and records;
9. reconciliation passes expected states and issue floors;
10. the bundle is content addressed;
11. runtime context selection matches the fixture;
12. strict review mode has not rejected visible review rows.

The public fixture normally produces a ready release while retaining twelve
review rows in the bundle. A ready release means the evidence boundary passed;
it does not mean every row is a supported result.

## Blocked state

A release is blocked when quality or runtime is rejected. Examples include:

- wrong requested context;
- a changed expected state;
- a missing source receipt;
- an unsupported issue code;
- a schema output omission;
- a lineage address mismatch;
- strict mode with visible controls;
- a missing C16 upstream address.

Blocked manifests remain useful for inspection because they retain the bundle,
quality, and record addresses. They must not be treated as release-ready data.

## Stable ordering

Source IDs follow fixture source order. Record IDs follow fixture record order.
Operation IDs follow the first receipt occurrence for each operation. Review rows
sort by descending priority and then record ID. These rules keep release diffs
stable and make replay comparisons meaningful.

## Output examples

```powershell
glio-noncode run-cell-state-frontier-pipeline --run-id cell-state-review --output pipeline.json
glio-noncode build-cell-state-frontier-release --run-id cell-state-review --output release.json
glio-noncode cell-state-frontier-trace --run-id cell-state-review --output trace.json
```

The Markdown rendering exposes the release ID, fixture version, run ID,
context, boundary, state, source IDs, bundle address, and records address. The
CSV receipt export exposes state and issue codes but never copies raw fixture
input.
