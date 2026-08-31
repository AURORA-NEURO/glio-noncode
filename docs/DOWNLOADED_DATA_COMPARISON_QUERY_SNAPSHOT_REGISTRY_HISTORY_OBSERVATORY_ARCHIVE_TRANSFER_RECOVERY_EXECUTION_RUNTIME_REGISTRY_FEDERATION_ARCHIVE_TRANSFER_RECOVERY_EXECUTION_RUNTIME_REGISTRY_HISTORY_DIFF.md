# Federation Runtime-Registry History Diff

The federation runtime-registry history diff compares two addressed history packages at the same snapshot ordinals. It is the review boundary for answering: what changed between a baseline registry history and a candidate registry history, and can the result be independently replayed?

## Contract

The diff accepts two histories with the same federation registry identity. Every ordinal is classified as exactly one of:

- `added`: only the candidate has an entry at the ordinal;
- `removed`: only the baseline has an entry;
- `changed`: both entries exist but their addressed registry snapshots differ;
- `unchanged`: both entries are byte-equivalent.

Each item preserves its stable ordinal identity, changed field names, left and right history-entry addresses, and both public snapshots. The summary also carries both history addresses, entry-count conservation, the latest-state direction (`improved`, `regressed`, `changed`, or `unchanged`), and acceptance. The boundary is deterministic: source histories are verified before comparison, items are ordinal-sorted, and every projection receives a content address.

## Persistence and assurance

`persist_diff` writes exactly four canonical files:

1. `manifest.json` — package identity, version, boundary, file list, and artifact addresses;
2. `diff.json` — the full comparison contract;
3. `items.json` — the independently addressed item collection;
4. `summary.json` — the bounded review projection.

Reload checks reject extra or missing files, symlinks, non-canonical JSON, tampered bytes, mismatched manifest addresses, and replay failures. The independent diff audit contains 16 checks covering version/boundary, both history addresses, identity and membership, change and field replay, direction, summary/items/manifest linkage, acceptance, public-boundary safety, and mapping round-trip.

## Query surface

The bounded query exposes eight ordered resources: `summary`, `items`, `added`, `removed`, `changed`, `unchanged`, `addresses`, and `bounds`. It supports resource selection, change filtering, key matching, text matching, offset, and limit. Query rows preserve the source resource semantics and receive their own addresses. The independent query audit contains 13 checks for version/boundary, filter replay, count replay, row order and membership, row-address replay, resource semantics, diff linkage, pagination bounds, public-boundary safety, and mapping round-trip.

## CLI and HTTP

The CLI command is the long public command ending in:

```text
...-runtime-registry-federation-archive-transfer-recovery-execution-runtime-registry-history-diff
```

It accepts two history directories or JSON documents:

```text
python -m glio_noncode <command> baseline-history candidate-history --destination diff-package --format summary
python -m glio_noncode <command>-audit diff-package --format summary
python -m glio_noncode <command>-query diff-package --change changed --format json --output diff-query.json
python -m glio_noncode <command>-query-audit diff-query.json --diff-input diff-package --format summary
```

The HTTP API mirrors this at `/v1/downloaded-data/.../runtime-registry/history/diff`. The build route accepts `left_input` and `right_input`; `/audit`, `/query`, and `/query/audit` operate on the persisted or JSON diff. Schema and capability routes are registered for the item, items, manifest, summary, diff, audit, query, and query-audit contracts.

## Downloaded-data demonstration

`examples/downloaded_data_contract_resolution_history_diff_policy_demo.py` builds the federation runtime registry from the attached downloaded ZIP, creates an empty baseline and ready candidate history, compares them, audits all 16 diff checks and all 13 query checks, persists the exact four-file package, and emits JSON review artifacts. The demo summary reports direction, item/change counts, addresses, audit counts, query counts, and artifact locations without exposing source paths, payload bytes, agent metadata, or language metadata.
