# Downloaded-data observatory archive transfer recovery

This contract turns a complete or partial history-observatory archive transfer
into a value-free recovery plan. It is designed for a receiver that has the
canonical transfer manifest and an arbitrary subset of validated chunks. The
plan contains no local path, source record, or payload bytes.

## Recovery states

`build_recovery` accepts an in-memory `ArchiveTransfer` or `TransferAssembler`.
`build_recovery_from_directory` accepts a persisted complete or partial transfer
directory and marks the resulting plan as checkpointed. A complete transfer has
no actions and the decision `assemble`. A partial transfer has one addressed
`RecoveryAction` for every missing chunk and the decision `resume`.

Every plan conserves the transfer chunk universe and archive bytes. The
`received_indices` and `missing_indices` sets are sorted, disjoint, and cover
every manifest index. `received_bytes + remaining_bytes` equals the archive
size. `next_index` is the first missing index, or `-1` when assembly is ready.
`safe_to_resume` is true only on a structurally valid plan; the decision still
tells the receiver whether it should request chunks or assemble.

## Independent audit

`audit_recovery` recomputes fifteen fixed checks outside the recovery builder:

- version and boundary replay;
- recovery address replay;
- index and byte conservation;
- missing-action coverage;
- action address and range replay;
- state, decision, and next-index replay;
- checkpoint-shape replay;
- public-boundary enforcement;
- canonical mapping round trip; and
- deterministic missing-action replay.

The audit has a canonical content address and JSON, CSV, and Markdown
projections. A malformed or tampered plan fails closed during typed
rehydration before an audit receipt is emitted.

## Bounded query

`query_recovery` provides six manifest-safe resources: `summary`, `actions`,
`received`, `missing`, `state`, and `bounds`. It supports resource selection,
chunk-index filtering, state filtering, received filtering, bounded text search,
offset, and limit. Rows are ordered by resource selection and ordinal and have
their own content addresses. Received rows deliberately retain only manifest-
safe identity because the recovery plan does not carry payload bytes or the
complete chunk table; missing and action rows retain the requested byte range
and chunk receipt.

`audit_query` replays the complete query specification and checks version,
boundary, resource order, filters, count, row order, row addresses, row
membership, resource semantics, recovery linkage, public boundary, and mapping
round trip.

## CLI

Use the existing long archive-transfer command and append `-recovery`:

```powershell
$base = "downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-observatory-archive-runtime-query-snapshot-diff-query-snapshot-diff-query-snapshot-registry-history-observatory-archive-transfer-recovery"

python -m glio_noncode $base C:\data\observatory-archive-transfer-partial `
  --format json --output C:\out\recovery.json

python -m glio_noncode "$base-verify" C:\out\recovery.json
python -m glio_noncode "$base-audit" C:\out\recovery.json --format markdown
python -m glio_noncode "$base-query" C:\out\recovery.json `
  --resource summary --resource missing --limit 32 --format json
python -m glio_noncode "$base-query-audit" C:\out\recovery.json `
  --resource summary --resource missing --limit 32 --format markdown
```

The base command also accepts the canonical observatory ZIP, a transfer JSON,
or an observatory directory. A persisted transfer directory is interpreted as
a checkpoint, so the plan reports `checkpointed: true` and exposes the exact
missing actions needed for continuation.

## API

The local HTTP API follows the archive transfer path:

```text
/v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy/package/registry/observatory/archive/runtime/query-snapshot/diff/query-snapshot/diff/query-snapshot/registry/history/observatory/archive/transfer/recovery
```

Use `?input=...&format=json` for a plan, `/verify` for typed rehydration,
`/audit` for independent checks, `/query` for bounded rows, and
`/recovery/query/audit` for query replay. Schema and capability routes are
available beneath `/recovery`, `/recovery/audit`, `/recovery/query`, and
`/recovery/query-audit`.

## Downloaded-data demonstration

The real ZIP demo at
`examples/downloaded_data_contract_resolution_history_diff_policy_demo.py`
builds the full comparison-query history observatory from the attached
downloaded archive, creates a 1,024-byte transfer, receives the first and last
chunks out of order, and emits both complete and partial recovery plans. Its
`summary.json` records state, decision, missing-action count, received and
remaining bytes, safety, checkpoint status, next index, audit counts, query
counts, and all recovery addresses. Recovery JSON, CSV, Markdown, and query
audit artifacts are written beside the transfer artifacts.
