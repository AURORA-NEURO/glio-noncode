# Persisted comparison-query snapshots

The comparison-query boundary can be sealed as a portable, value-free
handoff. This preserves the exact filtered page that was reviewed without
copying source record values or filesystem paths.

## Object graph

`build_snapshot` accepts one verified comparison query and emits an exact
five-file directory:

- `snapshot.json`: comparison identity, complete query shape, counts, state,
  and acceptance information;
- `query.json`: the exact bounded comparison-query page and row addresses;
- `audit.json`: the independently generated 12-check comparison-query audit;
- `summary.json`: a compact review projection; and
- `manifest.json`: canonical member order with size, hash, and content-address
  receipts for every artifact.

The handoff retains public comparison identities, source addresses, action
classes, directions, transitions, and bounded text. It does not retain source
record values, local paths, or attribution metadata. A handoff is `ready` only
when the nested query audit is accepted; otherwise it is `blocked`.

## Python surface

```python
from glio_noncode import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot as snapshot_model,
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_audit as audit_model,
)

snapshot = snapshot_model.run_snapshot(
    "path/to/comparison-query.json",
    snapshot_id="reviewed-comparison-page",
    destination="artifacts/reviewed-comparison-page",
)
audit = audit_model.audit_snapshot(snapshot)
assert snapshot.accepted and audit.accepted
reloaded = snapshot_model.load_snapshot("artifacts/reviewed-comparison-page")
assert reloaded.content_address == snapshot.content_address
```

The snapshot audit independently recomputes query linkage, nested query-audit
linkage, all query filters, counts, state and acceptance folding, summary and
manifest replay, every artifact byte receipt, mapping addresses, and the
public boundary. It has 15 fixed checks and fails closed for missing,
non-canonical, reordered, cross-linked, or tampered artifacts.

## CLI and HTTP

```powershell
glio-noncode downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-observatory-archive-runtime-query-snapshot-diff-query-snapshot-diff-query-snapshot `
  path/to/comparison-query.json `
  --snapshot-id reviewed-comparison-page `
  --destination artifacts/reviewed-comparison-page `
  --format summary

glio-noncode downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-observatory-archive-runtime-query-snapshot-diff-query-snapshot-diff-query-snapshot-audit `
  artifacts/reviewed-comparison-page --format markdown
```

The snapshot command supports `summary`, `json`, `csv`, and `markdown`
projections. The audit command returns success only for an accepted audit.
Schema and capability commands describe the manifest, summary, snapshot,
audit-check, and audit contracts.

The loopback HTTP API mirrors the operations at:

```text
/v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy/package/registry/observatory/archive/runtime/query-snapshot/diff/query-snapshot/diff/query-snapshot
/v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy/package/registry/observatory/archive/runtime/query-snapshot/diff/query-snapshot/diff/query-snapshot/audit
```

## Persistence guarantees

The member set is fixed to the five names above. Writes use a temporary sibling
directory and atomic replacement. Reloading requires regular files, canonical
UTF-8 JSON, exact member names, replayed content addresses, and matching
manifest receipts. Existing destinations require an explicit overwrite flag.
Symlinks, extra files, missing files, malformed documents, and stale nested
addresses are rejected.

The package is a review and transport primitive for downloaded-data workflows.
It reports structural and provenance facts from the supplied archive; it does
not make a clinical or scientific validity claim.
