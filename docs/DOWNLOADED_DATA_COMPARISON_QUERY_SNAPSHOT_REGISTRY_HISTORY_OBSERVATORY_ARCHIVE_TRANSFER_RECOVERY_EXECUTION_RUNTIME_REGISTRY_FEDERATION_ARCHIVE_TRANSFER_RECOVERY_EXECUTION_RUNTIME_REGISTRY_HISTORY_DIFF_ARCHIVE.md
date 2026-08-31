# Federation Runtime-Registry History-Diff Archive

The federation runtime-registry history-diff archive is the portable handoff
for a verified baseline/candidate history comparison. It packages the exact
four canonical history-diff projections inside a deterministic ZIP with one
outer manifest, so a diff can move between machines without carrying the
downloaded source archive, source paths, source records, or payload bytes.

## Contract

The archive is built only from the typed history-diff contract. The outer
manifest is `manifest.json`; the nested projections are:

1. `history-diff/manifest.json`
2. `history-diff/diff.json`
3. `history-diff/items.json`
4. `history-diff/summary.json`

The five-member ZIP has fixed member order, fixed DOS epoch timestamps,
regular-file permissions, DEFLATE level 9 compression, empty member comments,
and no archive comment. The outer envelope records the diff identity, diff
address, exact member list, per-member byte sizes and hashes, archive size,
and content address. Archive addressing excludes only the measured ZIP size,
which avoids a hash/size fixpoint while retaining byte-size verification.

## Verification and failure handling

Archive loading is fail-closed. It rejects duplicate, missing, reordered,
traversal, absolute, backslash-containing, symlink, encrypted, commented,
oversized, non-canonical, or tampered members. It reloads the nested diff,
replays its identity and four canonical projections, verifies every member
receipt, checks the outer manifest address, and confirms that regenerated ZIP
bytes exactly match the supplied bytes. Writes use an atomic replacement and
require explicit overwrite for an existing destination.

The independent archive audit has 18 checks spanning identity, boundary,
ordering, receipts, linkage, nested reload, projection replay, size, ZIP
safety, deterministic bytes, public-boundary safety, and mapping/byte
round-trips. The archive query exposes eight bounded resources:
`summary`, `manifest`, `artifacts`, `diff`, `items`, `changes`, `addresses`,
and `bounds`. It supports resource/key/text filters and deterministic
pagination. Its independent query audit has 13 checks for filter/count
replay, row order, row addresses, membership, resource semantics, bounds,
linkage, and public safety.

## CLI and HTTP

The CLI command is the history-diff command with `-archive` appended:

```text
python -m glio_noncode <history-diff-archive-command> diff-package --archive-id handoff-1 --destination diff.zip --format summary
python -m glio_noncode <history-diff-archive-command>-verify diff.zip --format summary
python -m glio_noncode <history-diff-archive-command>-audit diff.zip --format summary
python -m glio_noncode <history-diff-archive-command>-query diff.zip --resource changes --format json
python -m glio_noncode <history-diff-archive-command>-query-audit query.json --archive-input diff.zip --format summary
```

The local HTTP API mirrors the lifecycle at the history-diff `/archive`
route: build, verify, audit, query, query-audit, schemas, and capabilities.
All public projections are value-free and exclude local source paths,
downloaded records, raw payload bytes, agent metadata, and language metadata.

## Downloaded-data demonstration

`examples/downloaded_data_contract_resolution_history_diff_policy_demo.py`
builds the federation runtime-registry history diff from the attached
`GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip`. It then builds the
archive, replays deterministic bytes, writes the ZIP, reloads it through the
strict verifier, reruns all 18 archive checks, queries all eight resources,
and reruns all 13 query checks. The destination contains the ZIP plus JSON,
CSV, and Markdown projections for the envelope, archive audit, archive query,
and query audit.
