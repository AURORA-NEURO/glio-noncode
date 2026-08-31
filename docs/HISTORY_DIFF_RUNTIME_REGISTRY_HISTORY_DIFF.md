# Exact history-diff runtime-registry history diff

This contract compares two addressed longitudinal histories that were produced by the exact history-diff runtime admission registry. It is a public, deterministic projection over two already-addressed history objects.

The comparison is intentionally ordinal and identity constrained:

- both inputs must use the same registry identity;
- each ordinal becomes one stable comparison item;
- items are classified as `added`, `removed`, `changed`, or `unchanged`;
- changed fields follow the history entry contract order;
- each paired item retains both entry addresses and both bounded public snapshots;
- the summary derives counts, input history addresses, and an improved/regressed/changed/unchanged direction;
- empty histories remain valid inputs and cannot be mistaken for release-ready evidence.

The persisted diff package is exactly:

```text
manifest.json
diff.json
items.json
summary.json
```

Every document is canonical JSON. The manifest records the exact file set and artifact addresses. Reload verifies the file set, canonical bytes, nested component addresses, summary conservation, and the top-level content address. Non-canonical edits, unknown files, malformed nested objects, and tampered bytes are rejected.

Independent assurance is exposed through a fixed sixteen-check diff audit. The bounded query contract exposes eight resources:

```text
summary, items, added, removed, changed, unchanged, addresses, bounds
```

Query results are re-ordinalized, content addressed, paginated, and independently checked by a thirteen-check query audit.

CLI surface:

```text
python -m glio_noncode <exact-history-command>-diff <left-history> <right-history> --format summary
python -m glio_noncode <exact-history-command>-diff-audit <diff> --format summary
python -m glio_noncode <exact-history-command>-diff-query <diff> --change changed --format json
python -m glio_noncode <exact-history-command>-diff-query-audit <query.json> --diff-input <diff>
```

The exact command is the history command already registered for the history-diff archive-transfer recovery execution runtime registry history, followed by `-diff`. Its schema and capability commands use the same prefix with `-item-schema`, `-schema`, `-audit-schema`, `-query-schema`, and the corresponding capability/check suffixes.

The local HTTP route mirrors the CLI under the history route with `/diff`, `/diff/verify`, `/diff/audit`, `/diff/query`, `/diff/query/audit`, and the schema routes.

The public boundary excludes source paths, source records, payload bytes, private metadata, agent metadata, and language metadata. Only bounded public receipt fields, deterministic counters, addresses, and projections cross the contract.

The downloaded-data demo builds both histories from the supplied ZIP's registry receipts, compares them, persists and reloads the exact package, runs the independent audits and queries, and reports the resulting addresses and counts in its summary artifact.
