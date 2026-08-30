# Certificate-observatory archive registry

The certificate-observatory archive registry is the multi-snapshot coordination
boundary for `glio-noncode`. A certificate-observatory package represents one
verified downloaded handoff. Its ZIP archive preserves that package as one
addressed object. The registry adds a bounded catalog of those archives so a
release operator can compare replicas, group snapshots by package identity,
query held and accepted observations, and retain an append-only sequence of
catalog revisions.

The registry is intentionally additive. It does not merge histories, rewrite
observations, infer source files, or silently repair a package. An input is
accepted only after the existing package and archive verifiers have completed.
The public result retains content addresses and conserved counters; local input
paths are never copied into a registry entry.

## Boundary map

The plane is implemented as twelve focused modules:

| Module | Responsibility |
| --- | --- |
| `...archive_registry.py` | typed entries, package groups, metrics, index, canonical five-file persistence |
| `...archive_registry_audit.py` | sixteen independent structural, linkage, conservation, and replay checks |
| `...archive_registry_query.py` | bounded summary, entry, accepted, held, and package projections |
| `...archive_registry_query_audit.py` | fourteen independent query-result checks |
| `...archive_registry_diff.py` | archive-identity transition records and changed-field disclosure |
| `...archive_registry_diff_audit.py` | thirteen independent diff checks |
| `...archive_registry_diff_query.py` | bounded summary and change-type diff inspection |
| `...archive_registry_diff_query_audit.py` | fourteen independent diff-query checks |
| `...archive_registry_runtime.py` | package-directory, ZIP, JSON, persistence, and query composition |
| `...archive_registry_runtime_audit.py` | twelve runtime receipt checks |
| `...archive_registry_history.py` | append-only snapshots, predecessor links, and transition counters |
| `...archive_registry_history_audit.py` | fourteen history checks |

The modules share one address namespace family derived from the existing
certificate-observatory archive boundary. Every typed object has a replayable
content address. The address is calculated from the canonical public mapping
with its own address field removed. That makes mapping round trips and disk
replays testable without timestamps or mutable process state.

## Input forms

The runtime accepts any of the following for each archive input:

1. A canonical certificate-observatory package directory with exactly the
   package's expected JSON members.
2. A canonical certificate-observatory archive ZIP.
3. A JSON file containing a public archive mapping.
4. A JSON file containing a public package mapping, which is first materialized
   as an archive in memory.

The package directory is the normal input when working with ordinary downloaded
data. A ZIP is useful when a handoff has already crossed the transport boundary.
The runtime keeps the distinction clear: it loads and verifies the source, then
builds the registry entry from the addressed archive. A source path is never a
field on the entry, group, index, audit, query, diff, runtime, or history.

## Registry object

The core registry contains:

```text
registry_id
version
boundary
entries[]
entry_count
metrics{}
index{}
content_address
```

Each entry contains:

```text
entry_id
archive_id
archive_address
package_id
package_address
archive_size
accepted
observation_count
total_check_count
total_failed_count
alert_count
content_address
```

Entries are sorted by `entry_id`. `entry_id`, `archive_id`, and
`archive_address` are unique within one registry. The archive address points to
the independently verified ZIP object. The package address points to the
addressed eight-member package retained by that archive. The counters are
summaries only; the source archive remains the evidence object.

The metrics projection conserves every entry:

```text
entry_count = accepted_count + held_count
archive_bytes = sum(entry.archive_size)
observation_count = sum(entry.observation_count)
total_check_count = sum(entry.total_check_count)
total_failed_count = sum(entry.total_failed_count)
alert_count = sum(entry.alert_count)
unique_package_count = cardinality(entry.package_id)
```

The package index groups entries by `package_id`. Each group contains the sorted
entry IDs, the matching archive addresses, and accepted/held counters. The
index is a projection and is re-derived during construction, mapping reload,
and directory reload. A caller cannot supply a stale index and have it pass.

## Persistence contract

The registry directory contains exactly these five UTF-8 JSON files:

```text
manifest.json
registry.json
entries.json
metrics.json
index.json
```

There are no hidden sidecars, lock files, cache files, paths, timestamps, or
attribution fields. All JSON is canonical: sorted keys, stable separators, and
stable tuple-to-array conversion. The manifest records the expected member
order, each member's byte size, each member's hash, the registry address, and a
manifest address. Reload verifies:

1. the directory is regular and contains the exact member set;
2. every member is a regular file rather than a symlink;
3. every member is canonical JSON;
4. the manifest fields and file order replay;
5. every artifact size and hash matches its bytes;
6. the registry, entries, metrics, and index projections are mutually equal;
7. the registry content address replays;
8. the independent registry audit accepts.

Writes use a sibling staging directory and an atomic replacement. An existing
destination must be explicitly marked `overwrite=True`; a non-empty directory
is never silently reused. A failed replacement restores the previous
destination before re-raising the error.

## Registry construction

Build a registry from two package directories:

```powershell
python -m glio_noncode.cli `
  registry-federation-consensus-gate-certificate-observatory-archive-registry `
  --input C:\data\primary-observatory-package `
  --input C:\data\replica-observatory-package `
  --entry-id primary-entry `
  --entry-id replica-entry `
  --archive-id primary-archive `
  --archive-id replica-archive `
  --registry-id downloaded-observatory-registry `
  --destination C:\data\downloaded-observatory-registry `
  --format summary
```

The command loads both packages, builds the addressed archive envelopes, derives
the registry projections, writes the exact five-file directory, and emits a
path-free summary. The same command can use archive ZIPs or public JSON
documents in place of package directories. `--entry-id` and `--archive-id`
are repeatable and must line up one-for-one with `--input`.

The Python equivalent is:

```python
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_runtime as runtime

receipt = runtime.run_runtime(
    ("C:/data/primary-observatory-package", "C:/data/replica-observatory-package"),
    registry_id="downloaded-observatory-registry",
    entry_ids=("primary-entry", "replica-entry"),
    archive_ids=("primary-archive", "replica-archive"),
    destination="C:/data/downloaded-observatory-registry",
    limit=100,
)
assert receipt.accepted
```

The runtime receipt links the registry, its sixteen-check audit, and its query
result. It also reports whether persistence completed. It is a composition
receipt, not a replacement for the registry itself.

## Queries

Registry queries are bounded and addressable. Their resource vocabulary is:

```text
summary
entries
accepted
held
packages
```

Examples:

```powershell
python -m glio_noncode.cli `
  registry-federation-consensus-gate-certificate-observatory-archive-registry-query `
  --input C:\data\downloaded-observatory-registry `
  --resource summary `
  --resource entries `
  --resource packages `
  --package-id downloaded-observatory-package `
  --limit 100 `
  --format markdown
```

The query result contains the query mapping, registry ID, exact total/matched/
returned counts, next offset, truncation bit, ordered rows, and a result
address. Each row carries explicit evidence addresses. `accepted` and `held`
are views over the entry disposition; they do not change the registry.

The query auditor checks resource vocabulary, row order, filter behavior,
counter conservation, page boundaries, truncation, evidence linkage, public
boundary compliance, mapping replay, and result-address replay. A query can be
valid and empty: an empty filter match is not treated as a malformed registry.

## Diffs

Diffs match entries by `archive_id`. They retain only changed records; an
unchanged count remains on the diff summary. Each changed record discloses the
left and right entry/address links and the names of fields that changed.

```powershell
python -m glio_noncode.cli `
  registry-federation-consensus-gate-certificate-observatory-archive-registry-diff `
  --left C:\data\registry-before `
  --right C:\data\registry-after `
  --diff-id downloaded-observatory-transition `
  --format json `
  --output C:\data\registry-transition.json
```

The change vocabulary is `added`, `removed`, and `changed`. Added and removed
items have one side empty. Changed items have both sides and at least one
changed field. Matching entries with equal public mappings contribute to
`unchanged_count` and do not create a noisy item.

Inspect a diff without loading the source registries again:

```powershell
python -m glio_noncode.cli `
  registry-federation-consensus-gate-certificate-observatory-archive-registry-diff-query `
  --input C:\data\registry-transition.json `
  --resource summary `
  --resource added `
  --resource changed `
  --limit 100 `
  --format summary
```

The diff auditor recomputes side links, item order, added/removed/changed
shapes, changed fields, identity conservation, address replay, and bounded
limits. The diff-query auditor applies the same discipline to a projected
page. This keeps review tooling safe to run on files received from another
machine.

## Append-only history

Registry history retains a sequence of registry snapshots, not a mutable
current pointer. Every history entry contains a snapshot ID, registry address,
registry audit address, entry count, audit disposition, transition counters,
the predecessor registry address, and its own entry address.

```powershell
python -m glio_noncode.cli `
  registry-federation-consensus-gate-certificate-observatory-archive-registry-history `
  --input C:\data\registry-before `
  --input C:\data\registry-after `
  --snapshot-id baseline `
  --snapshot-id candidate `
  --history-id downloaded-observatory-history `
  --destination C:\data\downloaded-observatory-history `
  --format summary
```

The history counters conserve every adjacent diff:

```text
transition_count = entry_count - 1
added_count = sum(adjacent_diff.added_count)
removed_count = sum(adjacent_diff.removed_count)
changed_count = sum(adjacent_diff.changed_count)
```

The first entry has no predecessor. Every later entry points to the previous
registry address. Snapshot IDs and registry addresses are unique. The history
directory uses exactly four canonical files: `manifest.json`, `history.json`,
`entries.json`, and `metrics.json`. Reload validates member hashes, projections,
predecessor order, and address replay.

## HTTP surface

The local API exposes the plane below:

```text
/v1/registry/federation/consensus/gate/certificate/observatory/archive/registry
/v1/registry/federation/consensus/gate/certificate/observatory/archive/registry/audit
/v1/registry/federation/consensus/gate/certificate/observatory/archive/registry/query
/v1/registry/federation/consensus/gate/certificate/observatory/archive/registry/query-audit
/v1/registry/federation/consensus/gate/certificate/observatory/archive/registry/diff
/v1/registry/federation/consensus/gate/certificate/observatory/archive/registry/diff/audit
/v1/registry/federation/consensus/gate/certificate/observatory/archive/registry/diff/query
/v1/registry/federation/consensus/gate/certificate/observatory/archive/registry/diff/query-audit
/v1/registry/federation/consensus/gate/certificate/observatory/archive/registry/runtime
/v1/registry/federation/consensus/gate/certificate/observatory/archive/registry/runtime/audit
/v1/registry/federation/consensus/gate/certificate/observatory/archive/registry/history
/v1/registry/federation/consensus/gate/certificate/observatory/archive/registry/history/audit
```

The build and runtime routes accept repeated `input`, `entry_id`, and
`archive_id` query parameters. Build routes can persist to a destination when
the caller supplies one. Query, diff, and audit routes accept a persisted
directory or a public JSON document through `input`, `left`, or `right`.
`format=summary` is the default; JSON, CSV, and Markdown are available when
the contract provides that representation.

Every schema and capability document is also available below the same prefix.
The public-surface audit counts all registry-plane projections and rejects
forbidden attribution, language, process, secret, and path keys.

## Performance and limits

The core limit is 128 archive entries per registry and 128 snapshots per
history. Query pages are capped at 4,096 rows. Archive bytes are bounded by the
underlying archive limit and total registry input bytes are bounded by
`128 * MAX_ARCHIVE_BYTES`. These limits prevent a public request from creating
an unbounded object graph or response.

Construction is linear in the number of archive entries after each archive has
been verified. Sorting is bounded to the registry size. Package grouping uses a
single in-memory map and creates one deterministic group per package. Query
projection is linear in the projected row set and pagination slices only after
filtering. Diff matching uses two maps keyed by `archive_id`, so comparison is
linear in the two registry sizes. Persistence writes each canonical projection
once and hashes each member once.

The runtime intentionally avoids repeated archive loading. It materializes each
source exactly once, passes typed archives to the registry builder, and reuses
the resulting registry for audit and query. Persisted reloads are reserved for
the explicit disk-replay step or a caller's next command.

## Failure model

Expected failures are typed `ValidationError` instances and are safe to return
as bounded bad-request responses. Examples include:

| Failure | Result |
| --- | --- |
| missing source input | validation failure before construction |
| duplicate entry or archive ID | registry construction rejected |
| package/archive address mismatch | archive verifier rejects the source |
| extra registry file | directory reload rejected |
| symlinked registry member | directory reload rejected |
| noncanonical JSON | directory reload rejected |
| manifest hash drift | directory reload rejected |
| unsupported query resource | query construction rejected |
| page limit outside bounds | query construction rejected |
| changed item without both sides | diff mapping rejected |
| missing history predecessor | history mapping rejected |
| mismatched repeatable ID count | runtime/API/CLI rejects before source loading |

An audit report is different from a construction error. A malformed public
mapping can be represented as an incomplete audit report when that module's
contract supports it; a source that cannot be loaded or verified never becomes
a registry entry.

## Verification matrix

The focused contract suite covers:

| Area | Coverage |
| --- | --- |
| typed construction | entry derivation, sorting, grouping, uniqueness, metric conservation |
| canonical mapping | strict fields, round trips, address replay, public boundary |
| persistence | exact members, atomic replacement, overwrite policy, hash/tamper rejection |
| registry audit | all sixteen check IDs, serialized audit, CSV/Markdown/JSON output |
| registry query | all resources, filters, pagination, empty matches, row evidence |
| diff | added, removed, changed, unchanged, changed-field disclosure |
| diff query | resources, filtering, row ordinals, query replay |
| runtime | package directory loading, archive identity overrides, persistence, receipt audit |
| history | predecessor chain, adjacent counters, exact four-file replay |
| CLI | build, audit, query, diff, history, runtime, and schema commands |
| HTTP | schema routes, build, query, query audit, diff, and diff query |
| real-data path | existing downloaded-package demo now emits registry, diff, history, and runtime receipts |

Run the focused suite locally:

```powershell
python -m unittest tests.test_registry_federation_consensus_gate_certificate_observatory_archive_registry -q
```

Run the public inventory check:

```powershell
python -c "from glio_noncode.public_surface_audit import build_default_public_surface_audit; value = build_default_public_surface_audit(); print(value.accepted, len(value.checks))"
```

The downloaded-data demonstration remains the most useful end-to-end smoke
test because it begins at persisted replica registries and traverses the
federation, consensus, gate, certificate, observatory, archive, transfer,
recovery, archive-registry, diff, history, and disk-replay layers in one
path-free report.

## Health report and operator handoff

The registry report is the operator-facing projection over one verified
registry. It does not recompute a new source artifact or mutate the registry.
It joins the registry address with the independently computed registry-audit
address and a complete bounded query-result address, then derives the
readiness counters and actionable alerts. This keeps the report useful in a
review UI while retaining enough content-addressed evidence for a later
replay.

The report has three status values:

| Status | Meaning | Typical action |
| --- | --- | --- |
| `ready` | no held entries, failed checks, or alerts | continue to the next stage |
| `review` | evidence is held or source alerts are present, but no failed checks were recorded | inspect the linked entry evidence |
| `blocked` | at least one check failed or a critical alert is present | stop promotion and remediate the evidence |

The status is deliberately conservative. A source alert produces a review
signal even when every check passed. A failed check produces a critical alert
and blocks the report. This makes a clean audit and a clean operational
decision separate concepts: the audit can prove that the report is internally
consistent while the report can still truthfully say that the source is
blocked.

Each alert contains a compact kind, severity, message, zero or more entry
IDs, one or more content addresses, and its own alert address. The current
alert kinds are `held-entries`, `failed-checks`, and `observatory-alerts`.
Evidence addresses always point to public content-addressed values; local
paths, usernames, model names, language metadata, and attribution fields are
not included in the report projection.

Build a report from a persisted registry:

```powershell
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-observatory-archive-registry-report `
  --input C:\data\observatory-archive-registry --format markdown
```

For machine consumption, use JSON and pass the resulting document to the
independent report audit:

```powershell
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-observatory-archive-registry-report `
  --input C:\data\observatory-archive-registry --format json `
  --output C:\data\archive-registry-report.json
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-observatory-archive-registry-report-audit `
  --input C:\data\archive-registry-report.json --format summary
```

The report audit performs twenty checks covering address replay, all linked
namespaces, counter conservation, bounded counts, exact ratio replay, status
logic, deterministic alert ordering, evidence presence, public mapping
round-trip, export availability, and the public boundary. An accepted report
audit means the health projection is internally coherent; it does not override
the report status. A `blocked` report with an accepted report audit is the
expected result when downloaded evidence contains failed checks.

The equivalent HTTP routes are:

```text
/v1/registry/federation/consensus/gate/certificate/observatory/archive/registry/report
/v1/registry/federation/consensus/gate/certificate/observatory/archive/registry/report/audit
```

The report route accepts `input`, `report_id`, and `format`. The audit route
accepts a public report JSON document through `input`. `summary`, `json`,
`csv`, and `markdown` are supported where a representation is defined. The
schema and capability projections are available below `/report/` and
`/report/audit/` under the same versioned namespace.

## Downloaded-data walkthrough

The repository's real-data example accepts two already-downloaded canonical
package-registry directories. The data stays outside the repository; the
example reads it as input and emits only path-free summaries. The flow is:

```text
downloaded registry directories
        |
        v
federation + audit + gate + consensus
        |
        v
certificate + observatory + archive + transfer + recovery
        |
        v
archive registries (primary/replica)
        |
        +--> registry audit and bounded query
        +--> deterministic registry diff and diff query
        +--> append-only registry history
        +--> health report and report audit
        +--> canonical disk replay
```

Run it with the two downloaded registry directories supplied by the operator:

```powershell
python examples/registry_federation_real_downloaded_data_demo.py `
  --primary-registry C:\data\primary-registry `
  --replica-registry C:\data\replica-registry `
  --limit 10
```

The JSON result includes the report's status, alert count, acceptance and
failure ratios, the twenty-check report-audit summary, and the registry,
history, and runtime disk-replay booleans. If the source package contains
known held or failed evidence, a non-ready report is an informative result,
not a crash: the demo preserves that decision and the independent audit can
still be examined.
