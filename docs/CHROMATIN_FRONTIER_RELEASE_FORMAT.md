# Chromatin frontier release format

## Manifest

`build_chromatin_frontier_release` joins a quality report and runtime result into
a deterministic manifest. It contains:

| Field | Meaning |
| --- | --- |
| `release_id` | Content-derived release identifier |
| `fixture_id` | Public aggregate fixture identity |
| `fixture_version` | Fixture version string |
| `run_id` | Runtime invocation identity |
| `context_key` | Exact six-part biological and reference context |
| `evidence_boundary` | `public_aggregate_non_patient` |
| `release_state` | `ready` or `blocked` |
| `quality_address` | Quality report address |
| `bundle_address` | Full evidence bundle address |
| `record_address` | Sanitized receipt collection address |
| `source_ids` | Closed source receipt set |
| `operation_ids` | Four C13-C16 operation identifiers |
| `content_address` | Final manifest address |

The release state is `ready` only when quality is accepted and the runtime status
is accepted. A strict runtime that rejects visible review rows produces a blocked
manifest with the same diagnostic artifacts.

## Bundle contents

The bundle carries the data audit, 16 execution receipts, 120 evaluation checks,
replay report, 16 scenarios, policy rules and checks, four schema declarations,
lineage edges, reconciliation items, operation metrics, record IDs, and source
IDs. The records address is separate from the bundle address so downstream
consumers can compare record content without reprocessing every quality object.

Execution summaries are operation-specific:

- C13 retains observation count, segment count, ambiguous segment IDs, labels,
  and issues;
- C14 retains variant IDs, result count, directions, median deltas, and issues;
- C15 retains marker count, estimate count, aggregate value, spread, estimate
  states, and issues;
- C16 retains observation count, correction count, feature IDs, corrected signals,
  and issues.

Raw `input_text` is excluded from receipts, review views, CSV, and Markdown. The
fixture remains available as an input artifact for deterministic local replay.

## Review and trace

The view produces 12 review entries with priority and action. Out-of-domain and
invalid rows receive the highest priority, ambiguous replicate disagreement is
kept distinct from partial data, and every action states what must be checked
before reuse. The trace contains nine stage receipts and nine ordered completion
events. Each stage points to an addressable artifact.

## Reproducibility

The runtime does not fetch remote data. With the same fixture and run options,
adapter states, check IDs, receipt addresses, bundle address, and release inputs
are stable. Run timestamps and run IDs identify invocation context but do not
alter the scientific evidence objects inside the quality bundle.
