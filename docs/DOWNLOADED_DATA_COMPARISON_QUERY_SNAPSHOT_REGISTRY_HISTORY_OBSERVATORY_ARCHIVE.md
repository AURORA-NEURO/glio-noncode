# Comparison-query snapshot registry-history observatory archive

The history observatory archive is the transport boundary for the cross-history
comparison-query snapshot registry observatory. It packages the exact five-file
observatory handoff into one deterministic ZIP while retaining the nested
observatory identity, artifact addresses, and canonical byte receipts.

## Archive contract

Every archive has six members in fixed order:

1. `manifest.json`
2. `history-observatory/manifest.json`
3. `history-observatory/observatory.json`
4. `history-observatory/members.json`
5. `history-observatory/transitions.json`
6. `history-observatory/summary.json`

The manifest records the archive address, nested observatory address, member
names, sizes, hashes, and total archive size. ZIP timestamps, permissions,
compression settings, comments, member order, and JSON serialization are fixed
so the same observatory produces identical archive bytes and addresses.

`load_archive` is fail-closed. It rejects encrypted members, symlinks and
non-regular entries, path traversal, missing or extra members, out-of-order
members, non-canonical JSON, incorrect receipts, and nested replay failures.
`write_archive` uses an atomic replacement and refuses accidental overwrite by
default.

## Verification and inspection

The archive audit independently recomputes 17 checks covering archive identity,
manifest linkage, member vocabulary and order, byte receipts, nested
observatory projection, canonical bytes, ZIP replay, mapping round trips, size
conservation, and the nested observatory audit.

The archive query exposes bounded `summary`, `archive`, `artifacts`,
`observatory`, `members`, `histories`, `transitions`, `states`, and `trends`
resources. Filters include member name/hash, observatory/history/registry
identity, state, acceptance, transition, trend, address, and text. Results are
stable, paginated, content-addressed rows. Its independent query audit checks
the query shape, filter replay, counts, row order and addresses, resource
semantics, archive linkage, public boundary, and mapping round trip.

## CLI

The long-form command prefix is:

```text
downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-observatory-archive-runtime-query-snapshot-diff-query-snapshot-diff-query-snapshot-registry-history-observatory-archive
```

Build an archive from a persisted observatory directory:

```powershell
python -m glio_noncode <prefix> --input comparison-history-observatory --destination comparison-history-observatory-archive.zip --output archive.json
python -m glio_noncode <prefix>-verify --input comparison-history-observatory-archive.zip --output verification.json
python -m glio_noncode <prefix>-audit --input comparison-history-observatory-archive.zip --output audit.json
python -m glio_noncode <prefix>-query --input comparison-history-observatory-archive.zip --resource summary --resource histories --accepted true --output query.json
python -m glio_noncode <prefix>-query-audit --input comparison-history-observatory-archive.zip --resource summary --resource histories --accepted true --output query-audit.json
```

The corresponding HTTP base route is:

```text
/v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy/package/registry/observatory/archive/runtime/query-snapshot/diff/query-snapshot/diff/query-snapshot/registry/history/observatory/archive
```

`/verify`, `/manifest`, `/audit`, `/query`, and `/query/audit` are available
under that route. Schema and capability documents are registered in the same
public surface and exercised by continuous integration.

## Downloaded-data demonstration

The reproducible demo consumes the attached downloaded ZIP as data, derives two
comparison-query registry histories, folds them into an observatory, and emits
the archive plus JSON and Markdown audit/query artifacts:

```powershell
python examples/downloaded_data_contract_resolution_history_diff_policy_demo.py `
  C:\Users\murar\Downloads\GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip `
  artifacts\downloaded-data-contract-resolution-history-diff-policy-demo
```

The demo records the archive path, six-member vocabulary, archive size,
17-check archive audit result, query counts, query address, and 12-check query
audit result in `summary.json`.
