# Persisted diff-query snapshots

The runtime-query snapshot diff query can now be sealed as a portable,
value-free handoff. This closes the gap between inspecting a diff and sharing
the exact filtered page that was inspected.

## Object graph

`build_snapshot` accepts one verified runtime-query snapshot diff and the same
bounded filters as the diff-query plane. It produces:

- `snapshot.json`: source diff identity, query identity, endpoint snapshot
  identities, direction, state transition, counts, and acceptance state;
- `query.json`: the exact bounded page, including every row address;
- `audit.json`: the independently generated 12-check diff-query audit;
- `summary.json`: a compact review projection; and
- `manifest.json`: the canonical five-file list with size, hash, and content
  address receipts for each artifact.

The source diff itself is referenced by a content address. The handoff does not
copy source values or filesystem paths, so it can be reloaded without the
original archive or diff directory. A snapshot is `ready` only when the source
diff reconstructs and its query audit is accepted; otherwise it is `blocked`.

## Python surface

```python
from glio_noncode import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot as snapshot_model,
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_audit as audit_model,
)

snapshot = snapshot_model.run_snapshot(
    "path/to/runtime-query-snapshot-diff",
    snapshot_id="reviewed-changes",
    resources=("changed",),
    change="changed",
    destination="artifacts/reviewed-changes",
)
audit = audit_model.audit_snapshot(snapshot)
assert snapshot.accepted and audit.accepted
reloaded = snapshot_model.load_snapshot("artifacts/reviewed-changes")
assert reloaded.content_address == snapshot.content_address
```

The snapshot audit independently recomputes source/query/audit linkage, source
identities and transitions, counts, state and acceptance folding, summary and
manifest replay, every artifact byte receipt, mapping addresses, and the public
boundary. It has 15 fixed checks and fails closed when a required artifact is
missing, non-canonical, reordered, cross-linked, or tampered.

## CLI surface

```powershell
glio-noncode downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-observatory-archive-runtime-query-snapshot-diff-query-snapshot `
  path/to/runtime-query-snapshot-diff `
  --snapshot-id reviewed-changes `
  --resource changed `
  --change changed `
  --destination artifacts/reviewed-changes `
  --format summary

glio-noncode downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-observatory-archive-runtime-query-snapshot-diff-query-snapshot-audit `
  artifacts/reviewed-changes --format markdown
```

The snapshot command accepts `summary`, `json`, `csv`, and `markdown`
projections. The audit command returns exit code 0 only for an accepted audit
and exit code 2 for a failed audit.

Schema and capability commands are available for the manifest, summary,
snapshot, audit check, and audit contracts. The local HTTP API mirrors the
operations at:

```text
/v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy/package/registry/observatory/archive/runtime/query-snapshot/diff/query-snapshot
/v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy/package/registry/observatory/archive/runtime/query-snapshot/diff/query-snapshot/audit
```

## Persistence guarantees

The exact directory file set is fixed to the five names above. Writes use a
temporary sibling directory and an atomic replacement. Reloading requires
regular files, canonical UTF-8 JSON, exact member names, replayed content
addresses, and matching manifest receipts. Existing destinations require an
explicit overwrite flag. Symlinks, extra files, missing files, malformed
documents, and stale nested addresses are rejected.

The package is deliberately a review and transport primitive. It reports
structural and provenance facts from the downloaded archive workflow; it does
not turn the supplied product/planning ZIP into clinical evidence or make a
scientific validity claim.
