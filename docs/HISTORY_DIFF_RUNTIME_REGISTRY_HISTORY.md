# History-Diff Runtime Registry History

The exact history-diff runtime registry history layer records longitudinal snapshots of the exact runtime admission registry. Each snapshot is value-free and addressed, retains the same public `registry_id`, and links to the prior registry address so a reviewer can replay the sequence without source paths, payload bytes, private identifiers, agent metadata, or language metadata.

## Contract

The history model exposes four addressed objects: entries, manifest, summary, and history. The exact persisted package contains four canonical files:

- `manifest.json`
- `history.json`
- `entries.json`
- `summary.json`

Snapshots are ordered by ordinal and carry deterministic transitions: `initial`, `improved`, `regressed`, `unchanged`, or `changed`. The history state is `empty`, `ready`, or `blocked`; acceptance requires a non-empty sequence with a stable registry identity, valid ancestry, conserved counters, and replayable addresses.

The independent audit surface has 16 checks. The query surface provides seven bounded resources: `summary`, `snapshots`, `transitions`, `states`, `readiness`, `addresses`, and `bounds`. Query results support resource, state, key, transition, and text filters with deterministic pagination and an independent 12-check query audit.

## Interfaces

The exact command is the exact runtime registry command with `-history` appended. It supports build, verify, audit, query, query-audit, all 15 schema/capability commands, multiple `--registry-input` snapshots, and four output formats. The HTTP surface is the exact runtime registry API path with `/history` appended, with `/verify`, `/audit`, `/query`, `/query/audit`, and the matching schema routes.

The downloaded-data demo builds an empty and ready registry snapshot from the supplied ZIP-derived runtime receipts, persists and reloads the history package, re-audits every projection, queries every resource, and records the evidence in the demo summary and artifact inventory.

## Verification

Focused coverage exercises transition replay, canonical four-file persistence, reload equality, tamper rejection, CLI output, HTTP output, schema exposure, query filtering, query-audit linkage, and public-surface admission. The CI workflow runs all history schema commands and the focused test module on every change.
