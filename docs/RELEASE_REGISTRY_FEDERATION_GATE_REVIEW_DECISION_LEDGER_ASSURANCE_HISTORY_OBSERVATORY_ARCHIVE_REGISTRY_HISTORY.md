# Assurance history observatory archive registry history

The ordered registry history boundary records a sequence of independently
verified observatory archive registry packages. Each registry remains a
separate snapshot. The history adds deterministic adjacency and transition
summaries without merging source archives or introducing private metadata.

## Model

`RegistryHistory` contains one or more `RegistryHistorySnapshot` records and
zero or more `RegistryHistoryTransition` records. Snapshot ordinals start at
one. Transition ordinal `n` compares snapshot `n` with snapshot `n + 1`, so a
history with `N` snapshots has exactly `N - 1` transitions.

Each snapshot preserves the public registry identity, content address,
verification address, state, acceptance, release readiness, bounded metrics,
and entry count. Each transition preserves the underlying diff address,
added/removed/changed/unchanged item counts, registry-level changed fields,
and one of `unchanged`, `improved`, `regressed`, or `mixed`.

The history validates all cross-record relationships:

- snapshot ordinals are contiguous and bounded at 64;
- transitions are contiguous, adjacent, and bounded at 63;
- transition endpoints equal their neighboring snapshot addresses;
- state counts conserve the transition sequence;
- history endpoints equal the first and last snapshots;
- every snapshot and transition address replays from its public projection;
- public mappings reject path, language, agent, attribution, timestamp, and
  unknown metadata fields.

## Exact persistence

`write_history` writes an atomic directory containing exactly these four
canonical JSON files:

```text
manifest.json
history.json
snapshots.json
transitions.json
```

The manifest contains SHA-256 receipts and byte lengths for all four files.
`load_history` rejects missing or extra members, symlinks, non-canonical JSON,
receipt mismatches, projection mismatches, and invalid address linkage. An
existing destination requires explicit overwrite permission.

## Python

Build a timeline from already downloaded registry directories in their
meaningful chronological order:

```python
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history as history

value = history.build_history_from_directories(
    ("./registry-before", "./registry-after"),
    history_id="downloaded-release-history",
)
history.write_history(value, "./review-output/history")
print(value.summary())
```

The builder verifies each exact five-file registry package before producing
the history. Input order is preserved; the caller controls the sequence when
the downloaded packages represent time or release order.

## CLI

The long command name is intentionally stable across the CLI and HTTP
surfaces:

```text
python -m glio_noncode.cli \
  module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-packet-registry-federation-assurance-gate-review-decision-ledger-assurance-history-observatory-archive-registry-history \
  --registry ./registry-before \
  --registry ./registry-after \
  --history-id downloaded-release-history \
  --destination ./review-output/history \
  --format summary
```

Repeat `--registry` for each downloaded registry package. Use
`--allow-existing` only when intentionally replacing an exact compatible
history directory. The sibling commands `-history-verify` and
`-history-manifest` inspect an existing history package. The schema commands
are `-history-schema`, `-history-snapshot-schema`,
`-history-transition-schema`, and `-history-capabilities`.

The output formats are `json`, `csv`, `markdown`, and `summary`. Summary,
JSON, and Markdown are path-free public projections; CSV is a bounded row
projection of the ordered snapshots.

## HTTP

The build route is the `history` child of the archive registry route:

```text
/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/observatory/packet/registry/federation/assurance-gate/review/decision-ledger/assurance-history-series/release-registry/federation/gate/review/decision-ledger/assurance-history/observatory/archive/registry/history
```

Supply repeated `registry` query parameters, plus optional `history_id`,
`destination`, `allow_existing`, and `format=json|csv|markdown`. The route
also exposes `/schema`, `/snapshot-schema`, `/transition-schema`, and
`/capabilities`. Verification and manifest inspection are available at
`/verify` and `/manifest` with an `input` or `history` directory parameter.

## Downloaded-data demonstration

The standalone demo accepts one or more exact five-file registry directories
and can print or persist the resulting timeline:

```text
python examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_demo.py \
  --registry "$TEMP/glio-noncode-history-observatory-demo-current/registry-v1" \
  --registry "$TEMP/glio-noncode-history-observatory-demo-current/registry-v1" \
  --history-id downloaded-self-history \
  --format summary
```

Using the same real downloaded package twice produces two verified snapshots
and one deterministic `unchanged` transition. Supplying two different
downloaded registry packages exposes item-level additions, removals, changes,
readiness movement, and the aggregate transition state.
