# Workspace frontier failure modes

## Reading this guide

Failure states are part of the workspace contract. A failure is not always a
pipeline failure. Some failures are expected control outcomes that prove a
boundary is working. Use the issue code, state, and source receipt together.

## Failure classification

| Class | State | Release effect | Review effect |
| --- | --- | --- | --- |
| context boundary | out_of_domain | accepted control | withheld |
| missing selection | absent | accepted control | held |
| missing identity | abstained | accepted control | held |
| incomplete output | partial | accepted positive only when declared | held |
| typed input error | invalid | accepted control only | held |
| parser anomaly | partial | accepted control only | held |
| unexpected exception | invalid | gate failure | investigate immediately |

## Context mismatch

### Symptom

An execution returns `out_of_domain` and `context_mismatch`.

### Expected causes

- age group differs;
- treatment phase differs;
- territory differs;
- genome build differs;
- caller sent the wrong workspace context;
- track or cohort rows exist only in another context.

### Required behavior

Return no applicable records. Retain a warning and the requested context in the
output. Do not re-label the row as `absent`, because the source data exists but
does not apply to this request.

### Test evidence

`C01-CTRL-001`, `C02-CTRL-001`, `C03-CTRL-002`, and `C04-CTRL-002` cover this
mode across all four operations.

## Missing dossier

### Symptom

The case workspace is `partial` with `missing_dossier`.

### Expected causes

The case manifest includes variants and candidate elements but no dossier
snapshot. Hypothesis, evidence, or validation sections remain present as
sections, while their records are incomplete.

### Required behavior

Keep the variants and elements searchable. Keep the warning visible. Do not
invent hypothesis, evidence, or validation records.

## Invalid case input

### No variants

`CaseManifest` requires at least one variant. The evaluator maps this to
`invalid_workspace_input` and retains the validation message.

### Duplicate variant identity

Two rows with the same variant ID are rejected. The issue code is
`duplicate_variant_id`, which is more specific than the general invalid input
code. The output retains the original exception text for review.

### Invalid element

An element without a target gene or state is rejected by the typed model. A
future fixture can add this control while retaining the same issue taxonomy.

## Cohort absence

### Symptom

The cohort workspace is `absent` with `no_matching_records`.

### Expected causes

- all rows are non-callable while callability is required;
- the record set is empty;
- filters remove every exact-context row;
- the requested selection criteria do not match.

### Required behavior

Retain excluded counts and reasons. Do not return a supported empty table. Do
not convert a non-callable row into a selected row.

## Variant abstention

### Symptom

The variant detail is `abstained` with `variant_absent`.

### Expected causes

The exact variant ID is not in the containing workspace. Nearby coordinates,
shared labels, or a similar alternate allele are not sufficient for resolution.

### Required behavior

Return no variant record, an empty relationship set, and a warning. Keep the
containing workspace address so the caller can inspect the available records.

## Track parse issue

### Symptom

The track workspace is `partial` with `track_parse_issue`.

### Expected causes

A row has an invalid coordinate, malformed field, or unsupported record shape.
The parser returns the valid feature subset and a visible issue list.

### Required behavior

Keep successfully parsed features. Keep issue count and warning text. Keep the
track state partial. Do not silently drop the source row or report a fully
supported track.

## Invalid track input

### Symptom

The track operation is `invalid` with `invalid_track_input`.

### Expected causes

The input is empty or violates the parser contract before a batch can be
formed.

### Required behavior

Return an error payload with the state and issue code. Do not construct an
empty supported workspace to make the command appear successful.

## Unexpected failure

### Symptom

An error is not represented by the declared issue vocabulary, or a positive row
does not match its expected state.

### Triage sequence

1. Run `workspace-frontier-evaluate`.
2. Read `failed_check_ids`.
3. Print the matching fixture record.
4. Execute the underlying typed primitive directly.
5. Compare normalized coordinates, context keys, enum values, and issue codes.
6. Check whether an unordered mapping or runtime identifier entered an address.
7. Add or update a focused regression test.
8. Re-run the focused suite before the full suite.

Do not broaden the evaluator catch block to hide an unexpected error. Add a
declared issue code only when the boundary and tests explain the new state.

## Review disposition rules

| Condition | Disposition |
| --- | --- |
| supported, positive, no issues | ready |
| partial with explicit limitation | hold |
| absent or abstained | hold |
| invalid input | hold |
| context mismatch | withhold |
| control row with supported state | hold |

The default fixture has three ready rows and 13 held rows. This is expected and
should not be “fixed” by relaxing controls.

## Address drift

### Common sources

- wall-clock timestamps in fixture payloads;
- unordered source or record collections;
- mutable list reuse;
- enum strings not reconstructed on load;
- parser output order depending on input map iteration;
- a run ID included in deterministic execution payload;
- a warning assembled from a non-deterministic set.

### Detection

Run two replays and compare evaluation addresses and execution addresses. The
comparison should have no drift fields. The replay ID itself may differ; it is
not part of evaluation identity.

## Quality gate failures

### Evaluation passes, quality fails

Inspect schema field addresses, lineage edges, reconciliation rows, public
boundary, and accessibility retention.

### Reconciliation fails

Compare fixture expected values with execution values. A missing issue code is
usually more important than a changed display warning because the issue code is
part of the public contract.

### Release fails

Inspect bundle, quality, replay, runtime, public-boundary, and address checks.
The release manifest should remain in `hold` until the root cause is fixed.

## Data boundary incidents

If a future fixture accidentally includes individual-level data, stop the
release. Remove the affected fixture from the release candidate, review the
source receipt and export paths, and create a new fixture version after the
boundary is restored. Do not rely on a warning field alone.

## Performance limits

The threshold report explores page limits, offsets, interval spans, text modes,
and query modes. It verifies bounded values, not production throughput. A
performance regression should add a benchmark fixture separately from the
functional evidence gate.

## Security and privacy limits

The frontier retains source and content addresses but does not implement
identity, access control, encryption, or institutional data governance. A
release-ready aggregate fixture must not be interpreted as a complete privacy
review.

## Accessibility limits

Accessibility metadata proves that required labels and ordering are present in
the data contract. It does not prove browser focus behavior, screen-reader
announcements, contrast, reduced motion, or keyboard interaction in a client.

## Change management

When changing a failure mode:

1. update the contract issue vocabulary;
2. update the public control record;
3. update evaluator mapping;
4. update quality and depth checks;
5. update review-queue expectations;
6. update CLI tests;
7. update this guide;
8. run the full suite and both Actions lanes.
