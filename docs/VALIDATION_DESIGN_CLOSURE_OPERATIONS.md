# D13 validation-design closure operations

This document describes the portable closure layer for the C01–C04
validation-design handoff. The layer consumes the existing public aggregate
bundle and creates independent views over it. It does not alter the original
27-artifact bundle contract.

## Closure inventory

The current handoff has the following fixed denominators:

| Surface | Count | Meaning |
| --- | ---: | --- |
| exact-byte artifacts | 27 | JSON and CSV projections in the source bundle |
| manifest checks | 14 | original bundle checks |
| public sources | 5 | HTTPS source receipts |
| fixture records | 16 | four aggregate rows for each planning operation |
| operations | 4 | evidence gap, assay eligibility, MPRA, STARR-seq |
| executions | 16 | one result for each fixture record |
| evaluation checks | 80 | five checks per record |
| source runtime stages | 79 | normalized source runtime sequence |
| source runtime planes | 57 | accepted runtime projections |
| closure certification domains | 8 | independent release review domains |
| closure certification checks | 48 | six evidence-linked checks per domain |
| closure events | 158 | start and completion event for each source stage |
| closure metrics | 18 | bounded aggregate counters and acceptance signals |
| closure runtime stages | 12 | materialize through replay and finalization |

All counts are computed from the bundle and are also asserted by tests. They
are not estimates or documentation-only targets.

## Boundary

`validate_validation_design_closure_boundary` checks every hydrated artifact:

1. JSON bytes parse as JSON and CSV bytes remain a declared CSV artifact.
2. Every artifact has a safe relative path and unique path identity.
3. JSON and CSV media types agree with their file suffixes.
4. Every payload is present.
5. Recursive key discovery finds no attribution fields, model fields,
   programming-language fields, direct identity fields, email fields, or phone
   fields.
6. The report retains both discovered keys and rejected keys so a reviewer can
   see what was inspected.

The boundary only rejects prohibited fields. It does not rewrite or redact a
payload in place; exact bytes remain the source of truth.

## Address-only indexes

`build_validation_design_closure_indexes` creates deterministic indexes for:

- artifact ID and path;
- record ID and operation;
- evaluation check ID;
- runtime stage ID;
- runtime plane ID;
- issue code; and
- observed or expected state.

An index entry contains a lookup key, source resource, source ordinal, and
content address. It never embeds the original payload. `index_lookup` is a
small bounded resolver for a single index name and key. The index audit checks
conservation, non-empty coverage, positive ordinals, address presence, and the
27/16/80/79/57 denominators.

## Reconciliation

`reconcile_validation_design_closure` independently joins the fixture,
evaluation, runtime, and release projections. It verifies:

- every record has a source join;
- all sources are HTTPS receipts;
- execution IDs close against record IDs;
- every record has five evaluation checks;
- runtime sequence numbers are exactly `1..79`;
- stage output addresses are present;
- runtime plane IDs close against the source runtime;
- all planes are accepted;
- the runtime address matches the bundle manifest;
- release, summary, report, quality, observability, and access projections are
  accepted; and
- the review CSV has one row per record.

The report contains 33 addressed checks. A failure remains visible in
`failed_check_ids`; callers do not receive an implicit successful fallback.
`diff_validation_design_closure_bundles` compares exact artifact identities and
all closure resource counts, making a same-bundle replay an explicit empty
delta.

## Summary

`build_validation_design_closure_summary` emits three useful projections:

- counters for every conserved resource and acceptance signal;
- one operation summary per planning operation; and
- state and plane partitions for release review.

Operation summaries retain positive/control counts, passed/failed check counts,
accepted/blocked counts, issue families, and a content address. The summary
audit verifies that operation partitions sum back to the 16 records and 80
checks, state partitions sum back to records, and planes remain fully
accepted.

CSV and Markdown exports are deterministic. Neither export includes payload
bytes beyond the aggregate fields represented by the summary.

## Certification

The eight certification domains are:

1. manifest integrity;
2. public fixture coverage;
3. evaluation closure;
4. runtime trace;
5. address-only indexes;
6. public boundary;
7. offline query surface; and
8. release certification.

Each domain has six checks. Every check contains the observed value, required
value, detail, and an evidence tuple naming one or more bundle artifacts. A
certification report includes domain coverage, passed and failed totals,
failed IDs, and exact content addresses. The report is accepted only when all
48 checks pass.

## Query surface

`query_validation_design_closure` supports these resources:

```text
artifacts, records, executions, checks, sources, stages,
planes, operations, issues, states, reviews
```

Queries are bounded by offset and limit. Filters cover operation, role, state,
artifact kind, plane ID, stage ID, issue code, and text search. The query
returns the total before paging, the applied filter map, selected rows, and a
content address. CSV and Markdown renderers preserve deterministic ordering.

Example:

```powershell
python -m glio_noncode validation-design-frontier-bundle-closure-query `
  validation-design-bundle `
  --resource stages `
  --stage-id data-audit `
  --format markdown `
  --output data-audit-stage.md
```

## Observability

The closure observability projection emits two events per source runtime stage:
`stage_started` and `stage_completed`. Events retain sequence, stage ID, state,
input address, output address, detail, and their own content address. There are
158 events and the sequence is exactly `1..158`.

The 18 metrics cover artifact, manifest, record, source, operation, execution,
check, stage, plane, issue, state, review, ready-record, and acceptance
counts. Metrics are aggregate only; they do not expose row payloads or hidden
execution metadata.

## Runtime and replay

`run_validation_design_closure_runtime` orchestrates the complete closure:

```text
bundle-materialized
  -> boundary-validated
  -> indexes-built
  -> indexes-audited
  -> joins-reconciled
  -> summary-built
  -> summary-audited
  -> certification-completed
  -> observability-built
  -> observability-audited
  -> replay-verified
  -> runtime-finalized
```

Every stage has an input address, output address, state, detail, ordinal, and
content address. Replay materializes the source bundle twice with identical
inputs and compares both addresses to the expected bundle address. The final
runtime is ready only if every closure component and replay check is accepted.

## Failure rehearsal and export packet

`rehearse_validation_design_closure_failures` runs ten non-destructive negative
controls: missing payload, duplicate path, prohibited public key, execution
join gap, evaluation-check drift, unsafe source scheme, runtime sequence gap,
missing stage address, rejected plane, and review-row drift. Each probe must
observe a blocked condition and preserves its own addressed checks. The matrix
is accepted only when all ten mutations would be rejected.

`build_validation_design_closure_export` flattens the runtime into eleven
exact-byte artifacts, including boundary, indexes, reconciliation, summary,
certification, observability, replay, runtime, and failure-injection outputs.
`write_validation_design_closure_export` writes those bytes with a root
`closure-export.json` manifest. `verify_validation_design_closure_export`
recomputes every byte address, verifies safe unique paths, checks byte counts,
and rejects tampering. The export packet is therefore independently movable
between machines without importing the producer runtime.

`build_validation_design_closure_graph` adds a payload-free relationship view
over the same handoff. It connects the bundle to artifacts, fixture records,
sources, executions, checks, operations, runtime stages, runtime planes, and
review rows. Every edge is independently addressed, the graph must have one
connected component, and its audit requires unique edge identities and a
non-trivial node/edge floor. CSV export is available for graph review.

## API and CLI

The HTTP routes are:

```text
/v1/validation-design/bundle/closure-schema
/v1/validation-design/bundle/closure-query
/v1/validation-design/bundle/boundary
/v1/validation-design/bundle/indexes
/v1/validation-design/bundle/reconciliation
/v1/validation-design/bundle/summary
/v1/validation-design/bundle/certification
/v1/validation-design/bundle/closure-observability
/v1/validation-design/bundle/closure-runtime
/v1/validation-design/bundle/closure-failures
```

The CLI mirrors the routes with `validation-design-frontier-bundle-closure-*`
commands. Filesystem consumers can first create the original bundle, then run
each closure command against the destination without importing the producer
runtime.

## Release boundary

This closure layer is a research-use handoff. It supports review, audit,
reproducibility, and bounded planning inspection. It does not diagnose a
person, establish assay efficacy, infer an individual outcome, establish
causal certainty, or authorize a clinical or operational decision.
