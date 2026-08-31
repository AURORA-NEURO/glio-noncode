# Comparison-query snapshot registries

Persisted comparison-query snapshots can be admitted into one deterministic,
value-free registry. This gives a review or transfer boundary for a bounded set
of already sealed comparison pages without reopening the source archive.

## Registry package

`build_registry` accepts typed snapshots, snapshot mappings, or exact snapshot
handoff directories. It sorts entries by snapshot identity, rejects duplicate
snapshot IDs and content addresses, folds state and acceptance, and emits an
exact four-file directory:

- `registry.json`: registry identity, folded counts, state, acceptance, and the
  nested entry and manifest objects;
- `entries.json`: ordered snapshot identities, source diff/query/audit links,
  complete query shape, counts, state, and acceptance;
- `summary.json`: compact count and readiness projection; and
- `manifest.json`: canonical member order plus size, hash, and content-address
  receipts for `entries.json` and `summary.json`.

The registry retains public IDs, content addresses, filters, counts, states,
and bounded query metadata. It does not copy source record values or local
filesystem paths. A registry is `ready` only when every admitted snapshot is
ready and accepted; mixed or blocked inputs remain visible in the folded state.

## Python surface

```python
from glio_noncode import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_registry as registry_model,
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_registry_audit as audit_model,
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_registry_query as query_model,
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_registry_query_audit as query_audit_model,
)

registry = registry_model.run_registry(
    ["artifacts/comparison-page-a", "artifacts/comparison-page-b"],
    registry_id="reviewed-comparison-pages",
    destination="artifacts/reviewed-comparison-pages",
)
audit = audit_model.audit_registry(registry)
query = query_model.query_registry(
    registry,
    resources=("summary", "entries", "ready", "diffs", "queries"),
    accepted=True,
)
query_audit = query_audit_model.audit_query(query)
assert registry.accepted and audit.accepted and query_audit.accepted
reloaded = registry_model.load_registry("artifacts/reviewed-comparison-pages")
assert reloaded.content_address == registry.content_address
```

The independent registry audit has 16 checks covering ordering, identity,
snapshot linkage, query and diff conservation, state and acceptance folding,
document replay, manifest receipts, registry addressing, and the public
boundary. The bounded registry query exposes eight resources and its independent
query audit has 12 checks covering filter shape, pagination, row addresses,
partitions, projections, mapping replay, and public-surface conformance.

## CLI and HTTP

```powershell
glio-noncode downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-observatory-archive-runtime-query-snapshot-diff-query-snapshot-diff-query-snapshot-registry `
  artifacts/comparison-page-a artifacts/comparison-page-b `
  --registry-id reviewed-comparison-pages `
  --destination artifacts/reviewed-comparison-pages `
  --format summary

glio-noncode downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-observatory-archive-runtime-query-snapshot-diff-query-snapshot-diff-query-snapshot-registry-audit `
  artifacts/reviewed-comparison-pages --format markdown

glio-noncode downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-observatory-archive-runtime-query-snapshot-diff-query-snapshot-diff-query-snapshot-registry-query `
  artifacts/reviewed-comparison-pages --resource ready --accepted true --format json
```

The loopback HTTP API mirrors build, audit, query, and query-audit operations at
the registry, `/audit`, `/query`, and `/query/audit` suffixes below:

```text
/v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy/package/registry/observatory/archive/runtime/query-snapshot/diff/query-snapshot/diff/query-snapshot/registry
/v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy/package/registry/observatory/archive/runtime/query-snapshot/diff/query-snapshot/diff/query-snapshot/registry/audit
/v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy/package/registry/observatory/archive/runtime/query-snapshot/diff/query-snapshot/diff/query-snapshot/registry/query
/v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy/package/registry/observatory/archive/runtime/query-snapshot/diff/query-snapshot/diff/query-snapshot/registry/query/audit
```

Schema and capability commands describe every registry, audit, query, and
query-audit contract. The real downloaded-data demo builds two registry entries
from the attached ZIP-derived comparison flow, persists the four-file package,
reloads it, and verifies the registry and query audits.

## Persistence guarantees

Writes use a temporary sibling directory and atomic replacement. Reloading
requires exactly four regular files, canonical UTF-8 JSON, replayed registry and
entry addresses, matching nested documents, and matching manifest receipts.
Existing destinations require explicit overwrite. Symlinks, extra files,
missing files, malformed documents, stale nested addresses, duplicate snapshot
identity, and tampered bytes are rejected.

This registry is a structural review and transport primitive for downloaded-data
workflows. It reports facts from the supplied snapshots and makes no clinical or
scientific validity claim.
