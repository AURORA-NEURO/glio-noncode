# Assurance history observatory archive registry

The observatory archive registry is the cross-run coordination boundary for
already verified observatory ZIP files. It does not combine their source
histories. Each registry entry retains one archive content address, the
embedded observatory address, the embedded verification address, and bounded
state/counter projections. The registry fold is therefore auditable without
re-reading the source histories.

## Contract

The public module is:

```text
glio_noncode.assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry
```

It accepts `ObservatoryArchive` objects only after the archive verifier has
validated the embedded package. File helpers load exact ZIP archives and use
the file size only as a bounded transport metric; no source path is placed in
the public projection.

The aggregate state is a conservative fold:

| Entry condition | Registry state |
| --- | --- |
| no entries | `empty` |
| any blocked entry | `blocked` |
| otherwise any held entry | `held` |
| every entry ready, accepted, and release-ready | `ready` |
| any other non-empty combination | `mixed` |

`accepted` is true only when the registry is non-empty and every entry is
accepted. `release_ready` is true only when the folded state is `ready` and
every entry is release-ready. The eight-check verification artifact repeats
identity uniqueness, address reproduction, state/readiness projection,
counter conservation, public-boundary, and registry-address checks.

## Exact package

`write_registry` writes an atomic directory with exactly these five files:

```text
manifest.json
registry.json
entries.json
verification.json
metrics.json
```

The manifest contains four receipts for the non-manifest artifacts. Every JSON
document is canonical UTF-8 JSON. `load_registry` verifies the member set,
canonical encoding, manifest address, artifact receipts, entry linkage,
metrics linkage, verification linkage, and all derived content addresses.
Additional files, altered bytes, unknown fields, path-bearing values, and
forged addresses fail closed.

The registry address intentionally excludes the `verification_address` link
from its hash projection. This avoids a circular dependency: the verification
contains the registry address, while the registry publishes the verification
address. The link remains present in the public document and is checked by
the loader.

## Python example

```python
from pathlib import Path

from glio_noncode import (
    build_assurance_history_observatory_archive_registry_from_archive_files,
    load_assurance_history_observatory_archive_registry,
    query_assurance_history_observatory_archive_registry,
    write_assurance_history_observatory_archive_registry,
)

archives = (Path("observatory-one.zip"), Path("observatory-two.zip"))
value = build_assurance_history_observatory_archive_registry_from_archive_files(
    archives,
    entry_ids=("run-one", "run-two"),
)
write_assurance_history_observatory_archive_registry(value, "review-output/registry")
loaded = load_assurance_history_observatory_archive_registry("review-output/registry")
result = query_assurance_history_observatory_archive_registry(
    loaded,
    resource="entries",
    state="ready",
    limit=50,
)
print(result.to_dict())
```

The output is deterministic for the same archive bytes, registry identity,
entry identities, and verification identity. Source ordering is canonicalized
by entry ID before addresses and reports are produced.

## CLI

The command name follows the existing assurance-history observatory command
family. Repeat `--input` for each downloaded archive:

```powershell
python -m glio_noncode.cli `
  module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-packet-registry-federation-assurance-gate-review-decision-ledger-assurance-history-observatory-archive-registry `
  --input observatory-one.zip `
  --input observatory-two.zip `
  --entry-id run-one `
  --entry-id run-two `
  --destination review-output/registry `
  --format summary
```

Inspection commands are available for verification, manifest, bounded
queries, schemas, and capabilities:

```powershell
python -m glio_noncode.cli <registry-command>-verify --input review-output/registry
python -m glio_noncode.cli <registry-command>-manifest --input review-output/registry
python -m glio_noncode.cli <registry-command>-query --input review-output/registry --resource entries --format markdown
python -m glio_noncode.cli <registry-command>-capabilities
```

The registry query resources are `summary`, `entries`, `empty`, `ready`,
`held`, `blocked`, `mixed`, `accepted`, and `rejected`. Keyword, state,
acceptance, release-readiness, offset, and limit filters are bounded and
included in the query content address.

## HTTP API

The route is nested below the existing observatory archive boundary:

```text
/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/observatory/packet/registry/federation/assurance-gate/review/decision-ledger/assurance-history-series/release-registry/federation/gate/review/decision-ledger/assurance-history/observatory/archive/registry
```

Supported suffixes are:

| Route | Behavior |
| --- | --- |
| `/` | build from a comma-separated `input`/`archives` list and optionally persist with `destination` |
| `/verify` | load and verify an exact registry directory |
| `/manifest` | return the verified manifest |
| `/query` | return JSON, CSV, or Markdown registry query output |
| `/schema` | return the registry schema |
| `/entry-schema` | return the entry schema |
| `/metrics-schema` | return the metrics schema |
| `/verification-schema` | return the verification schema |
| `/verification-check-schema` | return the check schema |
| `/query-schema` | return the query schema |
| `/query-result-schema` | return the result schema |
| `/capabilities` | return limits, states, resources, and feature declarations |

All endpoint outputs are public projections. Local paths are request inputs
only and are not reflected in returned addresses, manifests, summaries, or
query records.

## Real downloaded archive demo

The runnable demo accepts one or more downloaded archive files, persists and
reloads the registry, and then queries it:

```powershell
python examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_demo.py `
  --input $env:TEMP\glio-noncode-history-observatory-demo-current\observatory.zip `
  --destination $env:TEMP\glio-noncode-history-observatory-demo-current\registry `
  --resource entries `
  --format markdown
```

The demo exercises downloaded bytes through the archive loader, not a source
directory shortcut. A successful run proves that the archive address, entry
address, registry address, verification address, exact five-file package, and
query address can all be recomputed after reload.

## Limits and safety

The registry accepts at most 128 entries, each with a bounded archive size.
Query windows are bounded. Entry IDs, archive addresses, and observatory
addresses must be unique. The implementation rejects symlinked inputs and
symlinked package members, requires explicit overwrite for an existing exact
package, and uses an atomic temporary-directory replacement for writes.

Registry membership does not imply scientific validity beyond the verified
contracts of the source observatory archives. It is a release-coordination and
audit surface, not a clinical decision system.
